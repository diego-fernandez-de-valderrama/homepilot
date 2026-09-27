"""Alembic environment.

The connection comes from `config.attributes["connection"]` when migrations run from
the application (`catalog-ingestion init` / `ingest`), otherwise from the
POSTGRES_* settings (`uv run alembic ...`).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from catalog_ingestion.core import PostgresSettings
from catalog_ingestion.database.catalog_database import CatalogDatabase
from catalog_ingestion.database.records import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("connection") is None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=PostgresSettings().url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = CatalogDatabase.create_engine(PostgresSettings())
    try:
        with engine.begin() as connection:
            _run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
