from importlib import resources
from typing import ClassVar

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from catalog_ingestion.core import PostgresSettings
from sqlalchemy import Engine, MetaData, create_engine, text
from sqlalchemy.engine import URL

from smart_home_agent.repositories.profile._records import MemoryBase


class MemoryDatabase:
    """The customer memory database: same server and credentials as the catalog (POSTGRES_*), another database.

    Creates it, builds its writable engine and migrates it; `METADATA` is the schema Alembic compares against.
    """

    METADATA: ClassVar[MetaData] = MemoryBase.metadata
    _MIGRATIONS_PACKAGE = "smart_home_agent.repositories.profile"

    def __init__(self, settings: PostgresSettings, name: str) -> None:
        self._settings = settings
        self._name = name

    @property
    def url(self) -> URL:
        return self._settings.url.set(database=self._name)

    def create_engine(self, connect_timeout: int = 10) -> Engine:
        """Writable engine (unlike the catalog engine, which is read-only)."""
        return create_engine(self.url, pool_pre_ping=True, connect_args={"connect_timeout": connect_timeout})

    def ensure_exists(self) -> bool:
        """Creates the database when it does not exist yet (connected to POSTGRES_DB). Returns True if created."""
        admin = create_engine(self._settings.url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 10})
        try:
            with admin.connect() as connection:
                exists = connection.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": self._name}
                )
                if exists.scalar() is not None:
                    return False
                quoted = connection.dialect.identifier_preparer.quote(self._name)
                connection.execute(text(f"CREATE DATABASE {quoted}"))
                return True
        finally:
            admin.dispose()

    @staticmethod
    def alembic_config() -> Config:
        """Alembic configuration that works from an installed package (no alembic.ini needed)."""
        config = Config()
        location = resources.files(MemoryDatabase._MIGRATIONS_PACKAGE) / "migrations"
        config.set_main_option("script_location", str(location))
        return config

    @staticmethod
    def upgrade_to_head(engine: Engine) -> None:
        """Applies all pending migrations (idempotent)."""
        config = MemoryDatabase.alembic_config()
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    @staticmethod
    def current_revision(engine: Engine) -> str | None:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
