"""End-to-end pipeline runs against the real PostgresRepository on a throwaway database (skipped when
PostgreSQL is unreachable), with in-memory Qdrant and fake Gemini components. The fake-based runs in
test_pipeline_idempotency.py cover more cases; these check that the real repository behaves the same."""

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import func, select

from catalog_ingestion.pipeline.orchestrator import IngestionPipeline, IngestOptions
from catalog_ingestion.storage.postgres.engine import create_session_factory, upgrade_to_head
from catalog_ingestion.storage.postgres.models import ProductRecord, RetrievalDocumentRecord
from catalog_ingestion.storage.postgres.repository import PostgresRepository
from catalog_ingestion.storage.qdrant.collection import ensure_collection
from catalog_ingestion.storage.qdrant.repository import QdrantRepository
from tests.conftest import build_zip, load_fixture_json
from tests.fakes import FakeEmbedder, FakeEnricher

pytestmark = pytest.mark.integration

DIMENSION = 8


@pytest.fixture
def real(tmp_path, empty_database, all_fixture_ids):
    upgrade_to_head(empty_database)
    sessions = create_session_factory(empty_database)
    client = QdrantClient(":memory:")
    ensure_collection(client, "products", DIMENSION)
    products = [load_fixture_json(pid) for pid in all_fixture_ids]
    qdrant = QdrantRepository(client, "products")
    pipeline = IngestionPipeline(
        postgres=PostgresRepository(sessions),
        qdrant=qdrant,
        embedder=FakeEmbedder(DIMENSION),
        web=None,
        enricher=FakeEnricher(),
        model_name=FakeEnricher.model,
    )
    return {
        "pipeline": pipeline,
        "sessions": sessions,
        "qdrant": qdrant,
        "products": products,
        "zip": build_zip(tmp_path / "products.zip", products),
        "tmp": tmp_path,
    }


def _scalar(sessions, statement):
    with sessions() as session:
        return session.scalar(statement)


def test_runs_are_idempotent_and_mark_documents_indexed(real):
    n = len(real["products"])
    first = real["pipeline"].ingest(IngestOptions(input_path=real["zip"])).as_dict()
    assert first["postgres_inserted"] == n and first["qdrant_indexed"] == n
    indexed = (
        select(func.count())
        .select_from(RetrievalDocumentRecord)
        .where(RetrievalDocumentRecord.indexed_doc_hash == RetrievalDocumentRecord.doc_hash)
    )
    assert _scalar(real["sessions"], indexed) == n

    second = real["pipeline"].ingest(IngestOptions(input_path=real["zip"])).as_dict()
    assert second["postgres_unchanged"] == n and second["llm_cached"] == n and second["qdrant_unchanged"] == n


def test_limit_runs_do_not_deactivate(real):
    n = len(real["products"])
    real["pipeline"].ingest(IngestOptions(input_path=real["zip"]))
    real["pipeline"].ingest(IngestOptions(input_path=real["zip"], limit=2))
    active = select(func.count()).select_from(ProductRecord).where(ProductRecord.active)
    assert _scalar(real["sessions"], active) == n


def test_removed_product_is_deactivated_and_reactivated_when_it_returns(real):
    n = len(real["products"])
    real["pipeline"].ingest(IngestOptions(input_path=real["zip"]))
    removed = real["products"][-1]["id"]
    smaller = build_zip(real["tmp"] / "smaller.zip", real["products"][:-1])

    stats = real["pipeline"].ingest(IngestOptions(input_path=smaller)).as_dict()
    assert stats["postgres_deactivated"] == 1 and stats["qdrant_deleted_inactive"] == 1
    assert _scalar(real["sessions"], select(ProductRecord.active).where(ProductRecord.id == removed)) is False
    cleared = select(RetrievalDocumentRecord.indexed_doc_hash).where(RetrievalDocumentRecord.product_id == removed)
    assert _scalar(real["sessions"], cleared) is None

    real["pipeline"].ingest(IngestOptions(input_path=real["zip"]))
    assert _scalar(real["sessions"], select(ProductRecord.active).where(ProductRecord.id == removed)) is True
    assert real["qdrant"].count() == n


def test_force_with_skip_llm_keeps_llm_output(real):
    n = len(real["products"])
    real["pipeline"].ingest(IngestOptions(input_path=real["zip"]))
    stats = real["pipeline"].ingest(IngestOptions(input_path=real["zip"], force=True, skip_llm=True)).as_dict()
    assert stats["llm_kept_previous"] == n
    with_output = select(func.count()).select_from(ProductRecord).where(ProductRecord.llm_output.is_not(None))
    assert _scalar(real["sessions"], with_output) == n
