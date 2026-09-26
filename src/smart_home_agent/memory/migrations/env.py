"""Alembic environment of the customer memory database.

The connection comes from `config.attributes["connection"]` when migrations run from the application
(`python -m smart_home_agent init-memory`), otherwise from the POSTGRES_* settings and AGENT_MEMORY_DB
(`uv run alembic ...` from smart-home-agent).
"""

from logging.config import fileConfig

from alembic import context
from catalog_ingestion.core.settings import PostgresSettings
from sqlalchemy import Connection

from smart_home_agent.config import AgentSettings
from smart_home_agent.memory.database import create_memory_engine, memory_url
from smart_home_agent.memory.models import Base

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
        url=memory_url(PostgresSettings(), AgentSettings().memory_db).render_as_string(hide_password=False),
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
    engine = create_memory_engine(PostgresSettings(), AgentSettings().memory_db)
    try:
        with engine.begin() as connection:
            _run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
