from collections.abc import Iterator

import pytest
from qdrant_client import QdrantClient
from sqlalchemy.exc import OperationalError

from smart_home_agent.config import Settings
from smart_home_agent.repositories.postgres import CatalogRepository, create_readonly_sessions


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.load()


@pytest.fixture(scope="session")
def catalog(settings: Settings) -> Iterator[CatalogRepository]:
    """The real catalog, read-only. Skipped when PostgreSQL is down or not ingested yet."""
    engine, sessions = create_readonly_sessions(settings.postgres.model_copy(update={}))
    repository = CatalogRepository(sessions)
    try:
        if repository.count_active() == 0:
            pytest.skip("catalog is empty (run catalog-ingestion first)")
    except OperationalError:
        pytest.skip("PostgreSQL not reachable (docker compose up -d in catalog-ingestion)")
    yield repository
    engine.dispose()


@pytest.fixture(scope="session")
def qdrant(settings: Settings) -> QdrantClient:
    from catalog_ingestion.storage.qdrant.collection import create_client

    client = create_client(settings.qdrant)
    try:
        if not client.collection_exists(settings.qdrant.collection):
            pytest.skip("Qdrant collection missing (run catalog-ingestion init + ingest)")
    except Exception:
        pytest.skip("Qdrant not reachable")
    return client
