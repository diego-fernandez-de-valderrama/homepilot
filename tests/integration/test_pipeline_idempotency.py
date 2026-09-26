"""End-to-end pipeline runs with in-memory Qdrant, an in-memory PostgreSQL fake,
fake Gemini components and real fixtures. No network, no Docker."""

from datetime import UTC, datetime
from typing import cast

import pytest
from qdrant_client import QdrantClient

from catalog_ingestion.domain.enrichment import WebPage
from catalog_ingestion.llm.errors import QuotaExhaustedError
from catalog_ingestion.llm.prompts import PROMPT_VERSION
from catalog_ingestion.pipeline.orchestrator import IngestionPipeline, IngestOptions
from catalog_ingestion.pipeline.stages import legacy_enrichment_hash, prepare
from catalog_ingestion.schemas.mappers import raw_from_schema
from catalog_ingestion.schemas.raw_product import RawProductSchema
from catalog_ingestion.storage.postgres.repository import PostgresRepository
from catalog_ingestion.storage.qdrant.collection import ensure_collection
from catalog_ingestion.storage.qdrant.repository import QdrantRepository
from catalog_ingestion.web.fetchers import FetchResult
from catalog_ingestion.web.retriever import WebRetriever
from tests.conftest import SPARSE_MATTER, build_zip, load_fixture_json
from tests.fakes import FakeEmbedder, FakeEnricher, InMemoryPostgres

DIMENSION = 8


class CountingFetcher:
    method = "http"

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, url):
        self.calls += 1
        return FetchResult(ok=False, method=self.method, http_status=403, error="HTTP 403")


@pytest.fixture
def env(tmp_path, all_fixture_ids):
    client = QdrantClient(":memory:")
    ensure_collection(client, "products", DIMENSION)
    products = [load_fixture_json(pid) for pid in all_fixture_ids]
    zip_path = build_zip(tmp_path / "products.zip", products)
    postgres = InMemoryPostgres()
    embedder = FakeEmbedder(DIMENSION)
    enricher = FakeEnricher()
    fetcher = CountingFetcher()
    qdrant = QdrantRepository(client, "products")
    pipeline = IngestionPipeline(
        # The in-memory fake implements the subset of PostgresRepository the pipeline uses.
        postgres=cast(PostgresRepository, postgres),
        qdrant=qdrant,
        embedder=embedder,
        web=WebRetriever([fetcher]),
        enricher=enricher,
        model_name=FakeEnricher.model,
    )
    return {
        "pipeline": pipeline,
        "postgres": postgres,
        "qdrant": qdrant,
        "embedder": embedder,
        "enricher": enricher,
        "fetcher": fetcher,
        "zip": zip_path,
        "products": products,
        "tmp": tmp_path,
    }


def test_second_run_is_a_no_op(env):
    n = len(env["products"])
    first = env["pipeline"].ingest(IngestOptions(input_path=env["zip"])).as_dict()
    assert first["postgres_inserted"] == n
    assert first["llm_called"] == n
    assert first["qdrant_indexed"] == n
    assert env["qdrant"].count() == n
    fetches = env["fetcher"].calls
    assert fetches == first["needs_web_enrichment"]

    second = env["pipeline"].ingest(IngestOptions(input_path=env["zip"])).as_dict()
    assert second["postgres_unchanged"] == n
    assert second["llm_cached"] == n
    assert second["qdrant_unchanged"] == n
    assert second["qdrant_indexed"] == 0
    assert env["enricher"].calls == n  # no new LLM calls
    assert len(env["embedder"].embedded_texts) == n  # no re-embedding
    assert env["fetcher"].calls == fetches  # cached web failures are not re-fetched
    assert env["qdrant"].count() == n  # no duplicates
    assert len(env["postgres"].products) == n


def test_modified_and_removed_products_are_updated(env):
    env["pipeline"].ingest(IngestOptions(input_path=env["zip"]))
    products = [dict(p) for p in env["products"]]
    changed = next(p for p in products if p["id"] == SPARSE_MATTER)
    changed["price"] = "99,95 €"
    removed = products.pop()
    zip_path = build_zip(env["tmp"] / "products_v2.zip", products)

    stats = env["pipeline"].ingest(IngestOptions(input_path=zip_path)).as_dict()

    assert stats["postgres_updated"] == 1
    assert stats["llm_called"] == 1  # only the changed product is re-enriched
    assert stats["qdrant_indexed"] == 1
    assert stats["postgres_deactivated"] == 1
    assert env["qdrant"].count() == len(products)
    assert env["postgres"].products[removed["id"]]["active"] is False
    assert env["qdrant"].indexed_states([removed["id"]]) == {}


def test_partial_runs_do_not_deactivate(env):
    stats = env["pipeline"].ingest(IngestOptions(input_path=env["zip"], only_products=(SPARSE_MATTER,))).as_dict()
    assert stats["selected"] == 1
    assert "postgres_deactivated" not in stats
    assert env["qdrant"].count() == 1


def test_force_recomputes_everything(env):
    n = len(env["products"])
    env["pipeline"].ingest(IngestOptions(input_path=env["zip"]))
    stats = env["pipeline"].ingest(IngestOptions(input_path=env["zip"], force=True)).as_dict()
    assert stats["llm_called"] == n
    assert stats["qdrant_indexed"] == n
    assert env["qdrant"].count() == n


def test_reindex_uses_postgres_only(env):
    n = len(env["products"])
    env["pipeline"].ingest(IngestOptions(input_path=env["zip"]))
    calls = env["enricher"].calls
    assert env["pipeline"].reindex().as_dict()["qdrant_indexed"] == 0
    assert env["pipeline"].reindex(force=True).as_dict()["qdrant_indexed"] == n
    assert env["enricher"].calls == calls


def test_new_embedding_model_triggers_reembedding(env):
    n = len(env["products"])
    env["pipeline"].ingest(IngestOptions(input_path=env["zip"]))
    env["pipeline"]._embedder = FakeEmbedder(DIMENSION, model="other-model")
    assert env["pipeline"].reindex().as_dict()["qdrant_indexed"] == n


def test_cached_web_page_is_reused_for_enrichment(env):
    url = load_fixture_json(SPARSE_MATTER)["url"].strip()
    env["postgres"].web_pages[url] = WebPage(
        url, True, "http", 200, "Kompatibel mit Apple Home.", None, datetime.now(UTC)
    )
    stats = env["pipeline"].ingest(IngestOptions(input_path=env["zip"], only_products=(SPARSE_MATTER,))).as_dict()
    assert stats["web_enrichment_successful"] == 1
    assert env["fetcher"].calls == 0


def test_skip_llm_keeps_deterministic_data(env):
    stats = env["pipeline"].ingest(IngestOptions(input_path=env["zip"], skip_llm=True)).as_dict()
    assert stats["llm_skipped"] == len(env["products"])
    assert env["enricher"].calls == 0


class QuotaEnricher(FakeEnricher):
    def enrich(self, product, facts, requirements, web_page):
        self.calls += 1
        raise QuotaExhaustedError("daily quota exhausted")


def test_daily_quota_stops_llm_calls_but_not_the_run(env):
    n = len(env["products"])
    enricher = QuotaEnricher()
    env["pipeline"]._enricher = enricher
    stats = env["pipeline"].ingest(IngestOptions(input_path=env["zip"], concurrency=1)).as_dict()

    assert enricher.calls == 1  # circuit breaker: no call after the first quota error
    assert stats["llm_failed"] == 1
    assert stats["llm_skipped_quota"] == n - 1
    assert stats["postgres_inserted"] == n  # deterministic data is still stored
    # Nothing is marked as LLM-enriched, so the next run retries every product.
    assert all(row["enrichment_hash"] is None for row in env["postgres"].products.values())

    env["pipeline"]._enricher = FakeEnricher()
    assert env["pipeline"].ingest(IngestOptions(input_path=env["zip"])).as_dict()["llm_called"] == n


class TransientFetcher(CountingFetcher):
    def fetch(self, url):
        self.calls += 1
        return FetchResult(ok=False, method="gemini_url_context", error="quota", transient=True)


def test_transient_web_failures_are_not_cached(env):
    fetcher = TransientFetcher()
    env["pipeline"]._web = WebRetriever([fetcher])
    first = env["pipeline"].ingest(IngestOptions(input_path=env["zip"])).as_dict()
    assert first["web_transient_failures_not_cached"] == first["needs_web_enrichment"]
    assert env["postgres"].web_pages == {}
    env["pipeline"].ingest(IngestOptions(input_path=env["zip"]))
    assert fetcher.calls == 2 * first["needs_web_enrichment"]  # retried on the next run


def test_changing_the_model_does_not_redo_enriched_products(env):
    n = len(env["products"])
    env["pipeline"].ingest(IngestOptions(input_path=env["zip"]))
    env["pipeline"]._model = "another-model"
    env["pipeline"]._enricher = FakeEnricher()
    stats = env["pipeline"].ingest(IngestOptions(input_path=env["zip"])).as_dict()
    assert stats["llm_cached"] == n
    assert env["pipeline"]._enricher.calls == 0
    # Provenance keeps the model that produced each output.
    document = env["postgres"].products[SPARSE_MATTER]["document"]
    assert document["enrichment_model"] == FakeEnricher.model


def test_results_stored_with_the_legacy_cache_key_are_reused_and_upgraded(env):
    n = len(env["products"])
    env["pipeline"].ingest(IngestOptions(input_path=env["zip"]))
    web_cache = env["postgres"].web_pages
    for raw_json in env["products"]:
        item = prepare(raw_from_schema(RawProductSchema.model_validate(raw_json), original=raw_json))
        url = item.product.source_url
        page = web_cache.get(url) if item.completeness.needs_web and url else None
        row = env["postgres"].products[item.product.id]
        row["enrichment_hash"] = legacy_enrichment_hash(item, page, FakeEnricher.model, PROMPT_VERSION)
        row["enrichment_model"] = FakeEnricher.model

    env["pipeline"]._enricher = FakeEnricher()
    stats = env["pipeline"].ingest(IngestOptions(input_path=env["zip"])).as_dict()
    assert stats["llm_cached"] == n and env["pipeline"]._enricher.calls == 0
    assert stats["postgres_updated"] == n  # stored again under the new key
    third = env["pipeline"].ingest(IngestOptions(input_path=env["zip"])).as_dict()
    assert third["postgres_unchanged"] == n


class InterruptingEnricher(FakeEnricher):
    def enrich(self, product, facts, requirements, web_page):
        if self.calls == 3:
            raise KeyboardInterrupt
        return super().enrich(product, facts, requirements, web_page)


def test_interrupted_run_keeps_finished_products_and_resumes(env):
    n = len(env["products"])
    env["pipeline"]._enricher = InterruptingEnricher()
    with pytest.raises(KeyboardInterrupt):
        env["pipeline"].ingest(IngestOptions(input_path=env["zip"], concurrency=1))
    assert env["postgres"].runs[-1]["status"] == "interrupted"
    saved = [row for row in env["postgres"].products.values() if row["enrichment_hash"] is not None]
    assert len(saved) == 3

    env["pipeline"]._enricher = FakeEnricher()
    stats = env["pipeline"].ingest(IngestOptions(input_path=env["zip"])).as_dict()
    assert stats["llm_cached"] == 3
    assert stats["llm_called"] == n - 3  # only the remaining products
