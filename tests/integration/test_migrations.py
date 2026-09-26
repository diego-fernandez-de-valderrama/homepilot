"""Alembic migrations against a real PostgreSQL (skipped when unreachable)."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from catalog_ingestion.storage.postgres.engine import alembic_config, upgrade_to_head
from catalog_ingestion.storage.postgres.models import Base

pytestmark = pytest.mark.integration

TABLES = {
    "products",
    "product_compatibility",
    "product_requirements",
    "web_pages",
    "retrieval_documents",
    "ingestion_runs",
}


def test_models_and_migrations_are_in_sync(empty_database):
    upgrade_to_head(empty_database)
    with empty_database.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)
    assert differences == [], "models changed without a migration: run `alembic revision --autogenerate`"


def test_upgrade_is_idempotent_and_downgrade_works(empty_database):
    upgrade_to_head(empty_database)
    upgrade_to_head(empty_database)
    assert set(inspect(empty_database).get_table_names()) >= TABLES

    config = alembic_config()
    with empty_database.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert set(inspect(empty_database).get_table_names()) == {"alembic_version"}

    upgrade_to_head(empty_database)
    assert set(inspect(empty_database).get_table_names()) >= TABLES
