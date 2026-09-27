from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError

from catalog_ingestion.core import PostgresSettings
from catalog_ingestion.database import CatalogDatabase


@pytest.fixture
def empty_database() -> Iterator[Engine]:
    """A freshly created `<POSTGRES_DB>_test` database; the real catalog is never touched.

    Skipped when PostgreSQL is not reachable (start it with `docker compose up -d`).
    """
    settings = PostgresSettings()
    test_settings = settings.model_copy(update={"db": f"{settings.db}_test"})
    admin = create_engine(settings.url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    try:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{test_settings.db}" WITH (FORCE)'))
            connection.execute(text(f'CREATE DATABASE "{test_settings.db}"'))
    except OperationalError:
        pytest.skip("PostgreSQL not reachable (start it with `docker compose up -d`)")
    finally:
        admin.dispose()

    engine = CatalogDatabase.create_engine(test_settings)
    yield engine
    engine.dispose()
