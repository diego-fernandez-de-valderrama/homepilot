"""Pipeline orchestration: stage ordering, concurrency, caching decisions and stats.

    load -> prepare (normalize, extract, completeness) -> web (if needed) -> LLM -> validate
         -> PostgreSQL upsert -> retrieval document -> embedding -> Qdrant upsert

Web and LLM calls run in a thread pool; all database writes happen on the main thread.
A failure in one product is logged and counted, and the run continues.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from catalog_ingestion.core.logging import log_fields
from catalog_ingestion.domain.enrichment import EnrichedProduct, WebPage
from catalog_ingestion.domain.enums import WebStatus
from catalog_ingestion.ingestion.zip_loader import LoadResult, load_products
from catalog_ingestion.llm.enricher import Enricher, LLMResult, from_cached_output
from catalog_ingestion.llm.errors import QuotaExhaustedError
from catalog_ingestion.llm.prompts import PROMPT_VERSION
from catalog_ingestion.pipeline.stages import PreparedProduct, enrichment_hash, legacy_enrichment_hash, prepare
from catalog_ingestion.pipeline.stats import NullProgress, ProgressSink, RunStats
from catalog_ingestion.retrieval.documents import RetrievalDocument, build_document
from catalog_ingestion.retrieval.embeddings import Embedder
from catalog_ingestion.schemas.mappers import payload_from_enriched
from catalog_ingestion.storage.postgres.repository import (
    PostgresRepository,
    ProductState,
    UpsertOutcome,
)
from catalog_ingestion.storage.qdrant.repository import QdrantRepository
from catalog_ingestion.validation.validator import Validator
from catalog_ingestion.web.retriever import WebRetriever

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestOptions:
    input_path: Path
    force: bool = False
    skip_web: bool = False
    skip_llm: bool = False
    refresh_web: bool = False
    only_products: tuple[str, ...] = ()
    limit: int | None = None
    concurrency: int = 4

    @property
    def is_full_run(self) -> bool:
        return not self.only_products and self.limit is None


@dataclass(frozen=True, slots=True)
class ProductResult:
    prepared: PreparedProduct
    enriched: EnrichedProduct | None
    fetched_page: WebPage | None  # newly fetched page to cache
    llm_output: dict[str, Any] | None
    enrichment_hash: str | None
    llm_status: str  # called | cached | skipped | skipped_quota | failed
    error: str | None = None


class IngestionPipeline:
    def __init__(
        self,
        postgres: PostgresRepository,
        qdrant: QdrantRepository | None,
        embedder: Embedder | None,
        web: WebRetriever | None,
        enricher: Enricher | None,
        model_name: str,
        validator: Validator | None = None,
        progress: ProgressSink | None = None,
        max_deactivate_ratio: float = 0.2,
    ) -> None:
        self._pg = postgres
        self._qdrant = qdrant
        self._embedder = embedder
        self._web = web
        self._enricher = enricher
        self._model = model_name
        self._validator = validator or Validator()
        self._progress = progress or NullProgress()
        self._max_deactivate_ratio = max_deactivate_ratio
        # Set when Gemini reports a quota that will not reset during this run (e.g. per day).
        self._llm_quota_exhausted = threading.Event()

    # --- ingest --------------------------------------------------------------------------

    def ingest(self, options: IngestOptions) -> RunStats:
        stats = RunStats()
        run_id = self._pg.start_run(
            {
                "command": "ingest",
                "input": str(options.input_path),
                "force": options.force,
                "skip_web": options.skip_web,
                "skip_llm": options.skip_llm,
                "refresh_web": options.refresh_web,
                "only_products": list(options.only_products),
                "limit": options.limit,
            }
        )
        status = "failed"
        try:
            self._ingest(options, stats)
            problems = ("failed", "qdrant_failed", "qdrant_delete_failed", "deactivation_skipped")
            status = "partial" if any(stats.get(key) for key in problems) else "succeeded"
        except KeyboardInterrupt:
            # Every product recorded before the interruption is already committed.
            status = "interrupted"
            raise
        finally:
            self._pg.finish_run(run_id, status, stats.as_dict())
        return stats

    def _ingest(self, options: IngestOptions, stats: RunStats) -> None:
        self._llm_quota_exhausted.clear()  # a new run may have a fresh quota
        loaded = load_products(options.input_path)
        stats.set("loaded", len(loaded.products))
        if loaded.errors:
            stats.set("load_errors", len(loaded.errors))

        raws = list(loaded.products)
        if options.only_products:
            wanted = set(options.only_products)
            raws = [raw for raw in raws if raw.id in wanted]
            missing = wanted - {raw.id for raw in raws}
            if missing:
                logger.warning("Requested products not found in input", extra=log_fields(ids=sorted(missing)))
        if options.limit is not None:
            raws = raws[: options.limit]
        stats.set("selected", len(raws))

        prepared = [prepare(raw) for raw in raws]
        stats.set("normalized", len(prepared))
        stats.set("needs_web_enrichment", sum(p.completeness.needs_web for p in prepared))

        states = self._pg.load_states()
        web_cache = self._pg.load_web_pages()

        def has_llm_output(item: PreparedProduct) -> bool:
            state = states.get(item.product.id)
            return state is not None and state.llm_output is not None

        done = sum(has_llm_output(item) for item in prepared)
        logger.info(
            "LLM enrichment plan",
            extra=log_fields(
                already_enriched=done,
                pending=len(prepared) - done,
                note="already enriched products are reused unless their input changed or --force is set",
            ),
        )
        # Already-enriched products first: they complete instantly, so progress reflects real work left.
        prepared.sort(key=lambda item: not has_llm_output(item))

        documents: list[tuple[EnrichedProduct, RetrievalDocument]] = []
        self._progress.start("enrich", len(prepared))
        pool = ThreadPoolExecutor(max_workers=options.concurrency)
        try:
            futures = [
                pool.submit(self._enrich_one, item, states.get(item.product.id), web_cache, options)
                for item in prepared
            ]
            for future in as_completed(futures):
                result = future.result()
                self._record(result, stats, documents)
                self._progress.advance("enrich")
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)
            raise
        pool.shutdown()
        self._progress.finish("enrich")

        if options.is_full_run:
            self._deactivate_missing(loaded, states, options, stats)
            self._delete_inactive_from_index(stats)

        self._index(documents, force=options.force, stats=stats)

    def _deactivate_missing(
        self, loaded: LoadResult, states: dict[str, ProductState], options: IngestOptions, stats: RunStats
    ) -> None:
        """Marks products missing from a full, cleanly loaded input as inactive.

        An empty input or unreadable files could otherwise deactivate products that still exist, so the
        step is skipped then; a large share of removals needs --force.
        """
        unreadable = [error for error in loaded.errors if not error.duplicate]
        if not loaded.products or unreadable:
            logger.warning(
                "Deactivation skipped: the input is empty or has unreadable files",
                extra=log_fields(loaded=len(loaded.products), unreadable=len(unreadable)),
            )
            stats.set("deactivation_skipped", 1)
            return
        present = {raw.id for raw in loaded.products}
        active = [pid for pid, state in states.items() if state.active]
        missing = [pid for pid in active if pid not in present]
        if not options.force and len(missing) > self._max_deactivate_ratio * len(active):
            logger.error(
                "Deactivation refused: too many products are missing from the input (use --force if intended)",
                extra=log_fields(missing=len(missing), active=len(active), max_ratio=self._max_deactivate_ratio),
            )
            stats.set("deactivation_skipped", 1)
            stats.set("deactivation_refused", len(missing))
            return
        stats.set("postgres_deactivated", len(self._pg.deactivate_missing(sorted(present))))

    def _delete_inactive_from_index(self, stats: RunStats) -> None:
        """Deletes the Qdrant points of every inactive product, not only of this run's removals, so a
        delete that failed before (after PostgreSQL already committed) is retried."""
        if self._qdrant is None:
            return
        inactive = self._pg.inactive_ids()
        if not inactive:
            return
        try:
            self._qdrant.delete(inactive)
        except Exception:
            logger.exception("Qdrant delete of inactive products failed; it is retried on the next run")
            stats.set("qdrant_delete_failed", len(inactive))
            return
        self._pg.clear_indexed(inactive)
        stats.set("qdrant_deleted_inactive", len(inactive))

    def _enrich_one(
        self,
        item: PreparedProduct,
        state: ProductState | None,
        web_cache: dict[str, WebPage],
        options: IngestOptions,
    ) -> ProductResult:
        """Runs in a worker thread: only external I/O (web, Gemini), no database access."""
        product_id = item.product.id
        try:
            web_status, web_page, fetched = self._web_stage(item, web_cache, options)

            llm_result: LLMResult | None = None
            llm_status = "skipped"
            input_hash = enrichment_hash(item, web_page, PROMPT_VERSION)
            if not options.force and state is not None and self._is_cached(item, state, web_page, input_hash):
                assert state.llm_output is not None
                # Keep the model that actually produced the output (provenance), whatever is configured now.
                llm_result = from_cached_output(
                    state.llm_output, state.enrichment_model or self._model, state.prompt_version or PROMPT_VERSION
                )
                llm_status = "cached"
            elif self._enricher is not None and not options.skip_llm and self._llm_quota_exhausted.is_set():
                llm_status = "skipped_quota"
            elif self._enricher is not None and not options.skip_llm:
                try:
                    llm_result = self._enricher.enrich(item.product, item.facts, item.requirements, web_page)
                    llm_status = "called"
                except QuotaExhaustedError as exc:
                    llm_status = "failed"
                    if not self._llm_quota_exhausted.is_set():
                        self._llm_quota_exhausted.set()
                        logger.error(
                            "Gemini quota exhausted: LLM enrichment is skipped for the rest of this run. "
                            "Products keep their deterministic data; re-run `ingest` later to enrich them.",
                            extra=log_fields(error=str(exc)),
                        )
                except Exception as exc:
                    llm_status = "failed"
                    logger.warning("LLM enrichment failed", extra=log_fields(product_id=product_id, error=str(exc)))

            enriched = self._validator.validate(
                product=item.product,
                completeness=item.completeness,
                facts=item.facts,
                requirements=item.requirements,
                web_status=web_status,
                web_page=web_page,
                llm=llm_result.enrichment if llm_result else None,
                enrichment_model=llm_result.model if llm_result else None,
                prompt_version=llm_result.prompt_version if llm_result else None,
            )
            return ProductResult(
                prepared=item,
                enriched=enriched,
                fetched_page=fetched,
                llm_output=llm_result.raw_output if llm_result else None,
                enrichment_hash=input_hash if llm_result else None,
                llm_status=llm_status,
            )
        except Exception as exc:
            logger.exception("Product processing failed", extra=log_fields(product_id=product_id))
            return ProductResult(item, None, None, None, None, "failed", error=f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _is_cached(item: PreparedProduct, state: ProductState, web_page: WebPage | None, input_hash: str) -> bool:
        if state.llm_output is None or state.enrichment_hash is None:
            return False
        if state.enrichment_hash == input_hash:
            return True
        # Results stored with the older key format (which included the model) are still valid.
        return state.enrichment_model is not None and state.enrichment_hash == legacy_enrichment_hash(
            item, web_page, state.enrichment_model, PROMPT_VERSION
        )

    def _web_stage(
        self, item: PreparedProduct, web_cache: dict[str, WebPage], options: IngestOptions
    ) -> tuple[WebStatus, WebPage | None, WebPage | None]:
        """Returns (status, page used for enrichment, newly fetched page to persist)."""
        url = item.product.source_url
        if not item.completeness.needs_web or url is None:
            return WebStatus.NOT_NEEDED, None, None
        cached = web_cache.get(url)
        can_fetch = self._web is not None and not options.skip_web
        if cached is not None:
            retry = can_fetch and (options.refresh_web or (self._web is not None and self._web.should_retry(cached)))
            if not retry:
                return (WebStatus.OK if cached.ok else WebStatus.FAILED), cached, None
        if not can_fetch:
            return WebStatus.SKIPPED, None, None
        assert self._web is not None
        page = self._web.retrieve(url)
        return (WebStatus.OK if page.ok else WebStatus.FAILED), page, page

    def _record(
        self, result: ProductResult, stats: RunStats, documents: list[tuple[EnrichedProduct, RetrievalDocument]]
    ) -> None:
        """Main thread: persist one product result and update counters."""
        product_id = result.prepared.product.id
        if result.fetched_page is not None:
            stats.inc("web_fetched")
            if result.fetched_page.transient:
                stats.inc("web_transient_failures_not_cached")
            else:
                self._pg.save_web_page(product_id, result.fetched_page)
        if result.enriched is None:
            stats.inc("failed")
            return
        enriched = result.enriched
        if enriched.web_status is WebStatus.OK:
            stats.inc("web_enrichment_successful")
        elif enriched.web_status is WebStatus.FAILED:
            stats.inc("web_enrichment_failed")
        elif enriched.web_status is WebStatus.SKIPPED:
            stats.inc("web_enrichment_skipped")
        stats.inc(f"llm_{result.llm_status}")
        stats.inc("validated")
        if enriched.validation_notes:
            stats.inc("validation_notes", len(enriched.validation_notes))

        try:
            outcome = self._pg.upsert_product(
                enriched, result.prepared.raw, result.prepared.raw_hash, result.enrichment_hash, result.llm_output
            )
        except Exception:
            logger.exception("PostgreSQL upsert failed", extra=log_fields(product_id=product_id))
            stats.inc("failed")
            return
        stats.inc(f"postgres_{outcome.value}")
        if outcome is not UpsertOutcome.UNCHANGED:
            stats.inc("postgres_upserted")

        document = build_document(enriched)
        self._pg.save_document(document)
        documents.append((enriched, document))

    # --- indexing ------------------------------------------------------------------------

    def _index(self, documents: list[tuple[EnrichedProduct, RetrievalDocument]], force: bool, stats: RunStats) -> None:
        if self._qdrant is None or self._embedder is None:
            stats.set("qdrant_skipped_no_embedder", len(documents))
            logger.warning("Embedding/Qdrant stage skipped: no embedder configured (GEMINI_API_KEY missing?)")
            return
        model_id = self._embedder.model_id
        indexed = self._qdrant.indexed_states([doc.product_id for _, doc in documents])
        pending = [
            (enriched, doc)
            for enriched, doc in documents
            if force
            or (state := indexed.get(doc.product_id)) is None
            or state.doc_hash != doc.doc_hash
            or state.embedding_model != model_id
        ]
        stats.set("qdrant_unchanged", len(documents) - len(pending))
        if not pending:
            stats.set("qdrant_indexed", 0)
            return

        self._progress.start("embed", len(pending))
        indexed_count = 0
        batch_size = 50
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            try:
                vectors = self._embedder.embed_documents([doc.text for _, doc in batch])
                self._qdrant.upsert(
                    [
                        (payload_from_enriched(enriched, doc.doc_hash, model_id), vector)
                        for (enriched, doc), vector in zip(batch, vectors, strict=True)
                    ]
                )
                self._pg.mark_indexed([doc for _, doc in batch], model_id)
                indexed_count += len(batch)
            except Exception:
                logger.exception("Embedding/Qdrant batch failed", extra=log_fields(batch_start=start, size=len(batch)))
                stats.inc("qdrant_failed", len(batch))
            self._progress.advance("embed", len(batch))
        self._progress.finish("embed")
        stats.set("qdrant_indexed", indexed_count)

    # --- reindex -------------------------------------------------------------------------

    def reindex(self, force: bool = False) -> RunStats:
        """Rebuild retrieval documents and embeddings from PostgreSQL (no web, no LLM)."""
        stats = RunStats()
        run_id = self._pg.start_run({"command": "reindex", "force": force})
        status = "failed"
        try:
            self._delete_inactive_from_index(stats)
            products = self._pg.load_enriched()
            stats.set("loaded_from_postgres", len(products))
            documents = []
            for enriched in products:
                document = build_document(enriched)
                self._pg.save_document(document)
                documents.append((enriched, document))
            self._index(documents, force=force, stats=stats)
            status = "partial" if stats.get("qdrant_failed") or stats.get("qdrant_delete_failed") else "succeeded"
        finally:
            self._pg.finish_run(run_id, status, stats.as_dict())
        return stats
