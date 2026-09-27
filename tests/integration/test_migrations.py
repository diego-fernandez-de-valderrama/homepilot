"""Alembic migrations against a real PostgreSQL (skipped when unreachable)."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, inspect, text
from sqlalchemy.exc import IntegrityError

from catalog_ingestion.database import Base, CatalogDatabase, PostgresRepository
from catalog_ingestion.enrichment import Validator
from catalog_ingestion.preparation import ProductPreparer
from catalog_ingestion.vocabulary import WebStatus
from tests.conftest import BOSCH_CONTROLLER, load_raw

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
    CatalogDatabase.upgrade_to_head(empty_database)
    with empty_database.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)
    assert differences == [], "models changed without a migration: run `alembic revision --autogenerate`"


def test_upgrade_is_idempotent_and_downgrade_works(empty_database):
    CatalogDatabase.upgrade_to_head(empty_database)
    CatalogDatabase.upgrade_to_head(empty_database)
    assert set(inspect(empty_database).get_table_names()) >= TABLES

    config = CatalogDatabase.alembic_config()
    with empty_database.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert set(inspect(empty_database).get_table_names()) == {"alembic_version"}

    CatalogDatabase.upgrade_to_head(empty_database)
    assert set(inspect(empty_database).get_table_names()) >= TABLES


def test_check_constraints_match_the_models(empty_database):
    CatalogDatabase.upgrade_to_head(empty_database)
    inspector = inspect(empty_database)
    for table in Base.metadata.sorted_tables:
        expected = {
            str(constraint.name)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint) and constraint.name
        }
        actual = {c["name"] for c in inspector.get_check_constraints(table.name)}
        assert expected <= actual, table.name


@pytest.mark.parametrize(
    ("table", "column", "value", "constraint"),
    [
        ("products", "completeness_level", "Rich", "products_completeness_level_check"),
        ("product_compatibility", "status", "Supported", "product_compatibility_status_check"),
        ("product_compatibility", "confidence", "1.5", "product_compatibility_confidence_check"),
    ],
)
def test_enum_columns_reject_unknown_values(empty_database, table, column, value, constraint):
    CatalogDatabase.upgrade_to_head(empty_database)
    prepared = ProductPreparer.prepare(load_raw(BOSCH_CONTROLLER))
    enriched = Validator().validate(
        prepared.product, prepared.completeness, prepared.facts, prepared.requirements,
        WebStatus.NOT_NEEDED, None, None, None, None,
    )  # fmt: skip
    PostgresRepository(CatalogDatabase.session_factory(empty_database)).upsert_product(
        enriched, prepared.raw, prepared.raw_hash, None, None
    )
    with pytest.raises(IntegrityError, match=constraint), empty_database.begin() as connection:
        connection.execute(text(f"UPDATE {table} SET {column} = :value"), {"value": value})
