from importlib import resources

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from catalog_ingestion.core import PostgresSettings


class CatalogDatabase:
    """Engine, sessions and schema migrations of the catalog database."""

    MIGRATIONS_PACKAGE = "catalog_ingestion.database"

    @staticmethod
    def create_engine(settings: PostgresSettings) -> Engine:
        return create_engine(settings.url, pool_pre_ping=True, connect_args={"connect_timeout": 10})

    @staticmethod
    def session_factory(engine: Engine) -> sessionmaker[Session]:
        return sessionmaker(engine, expire_on_commit=False)

    @staticmethod
    def alembic_config() -> Config:
        """Alembic configuration that works from an installed package (no alembic.ini needed)."""
        config = Config()
        migrations = resources.files(CatalogDatabase.MIGRATIONS_PACKAGE) / "migrations"
        config.set_main_option("script_location", str(migrations))
        return config

    @staticmethod
    def upgrade_to_head(engine: Engine) -> None:
        """Apply all pending migrations (idempotent)."""
        config = CatalogDatabase.alembic_config()
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
