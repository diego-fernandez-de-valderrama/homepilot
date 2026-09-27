"""Engine, database creation and migrations of the customer memory database."""

from importlib import resources

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from catalog_ingestion.core.settings import PostgresSettings
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL

MIGRATIONS_PACKAGE = "smart_home_agent.memory"


def memory_url(settings: PostgresSettings, database: str) -> URL:
    """Same server and credentials as the catalog (POSTGRES_*), another database."""
    return settings.url.set(database=database)


def create_memory_engine(settings: PostgresSettings, database: str, connect_timeout: int = 10) -> Engine:
    """Writable engine (unlike the catalog engine, which is read-only)."""
    return create_engine(
        memory_url(settings, database), pool_pre_ping=True, connect_args={"connect_timeout": connect_timeout}
    )


def ensure_database(settings: PostgresSettings, database: str) -> bool:
    """Creates the database when it does not exist yet (connected to POSTGRES_DB). Returns True if created."""
    admin = create_engine(settings.url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 10})
    try:
        with admin.connect() as connection:
            exists = connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database})
            if exists.scalar() is not None:
                return False
            quoted = connection.dialect.identifier_preparer.quote(database)
            connection.execute(text(f"CREATE DATABASE {quoted}"))
            return True
    finally:
        admin.dispose()


def alembic_config() -> Config:
    """Alembic configuration that works from an installed package (no alembic.ini needed)."""
    config = Config()
    config.set_main_option("script_location", str(resources.files(MIGRATIONS_PACKAGE) / "migrations"))
    return config


def upgrade_to_head(engine: Engine) -> None:
    """Applies all pending migrations (idempotent)."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()
