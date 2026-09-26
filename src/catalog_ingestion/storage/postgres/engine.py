"""Engine, sessions and schema migrations."""

from importlib import resources

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from catalog_ingestion.core.settings import PostgresSettings

MIGRATIONS_PACKAGE = "catalog_ingestion.storage.postgres"


def create_db_engine(settings: PostgresSettings) -> Engine:
    return create_engine(settings.url, pool_pre_ping=True, connect_args={"connect_timeout": 10})


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def alembic_config() -> Config:
    """Alembic configuration that works from an installed package (no alembic.ini needed)."""
    config = Config()
    config.set_main_option("script_location", str(resources.files(MIGRATIONS_PACKAGE) / "migrations"))
    return config


def upgrade_to_head(engine: Engine) -> None:
    """Apply all pending migrations (idempotent)."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
