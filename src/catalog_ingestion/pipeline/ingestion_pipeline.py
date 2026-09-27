import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from catalog_ingestion.core import LogSetup
from catalog_ingestion.database import PostgresRepository
from catalog_ingestion.enrichment import Enricher, ProductEnricher, Validator, WebRetriever
from catalog_ingestion.indexing import Embedder, QdrantRepository, RetrievalDocumentBuilder
from catalog_ingestion.models import EnrichedProduct, ProductState, RetrievalDocument
from catalog_ingestion.pipeline._deactivator import Deactivator
from catalog_ingestion.pipeline._index_writer import IndexWriter
from catalog_ingestion.pipeline._product_recorder import ProductRecorder
from catalog_ingestion.pipeline.ingest_options import IngestOptions
from catalog_ingestion.pipeline.null_progress import NullProgress
from catalog_ingestion.pipeline.progress_sink import ProgressSink
from catalog_ingestion.pipeline.run_stats import RunStats
from catalog_ingestion.preparation import PreparedProduct, ProductPreparer, ZipLoader

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Drives the stages of a run and records it (`ingestion_runs`).

    ingest:  load -> prepare -> enrich (web, LLM, validate; thread pool) -> PostgreSQL -> deactivate -> index
    reindex: PostgreSQL -> retrieval documents -> embeddings -> Qdrant (no web, no LLM)

    Web and LLM calls run in a thread pool; all database writes happen on the main thread.
    A failure in one product is logged and counted, and the run continues.
    """

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
        self._progress = progress or NullProgress()
        self._enricher = ProductEnricher(web, enricher, validator or Validator(), model_name)
        self._recorder = ProductRecorder(postgres)
        self._index_writer = IndexWriter(postgres, qdrant, embedder, self._progress)
        self._deactivator = Deactivator(postgres, qdrant, max_deactivate_ratio)

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

    def reindex(self, force: bool = False, recreate: Callable[[], None] | None = None) -> RunStats:
        """Rebuild retrieval documents and embeddings from PostgreSQL (no web, no LLM).

        With `recreate`, every document is embedded first and the collection is only recreated
        (through the callback) once all embeddings succeeded, so a failure never leaves it empty.
        """
        stats = RunStats()
        run_id = self._pg.start_run({"command": "reindex", "force": force, "recreate": recreate is not None})
        status = "failed"
        try:
            if recreate is None:
                self._deactivator.delete_inactive_from_index(stats)
            products = self._pg.load_enriched()
            stats.set("loaded_from_postgres", len(products))
            documents = []
            for enriched in products:
                document = RetrievalDocumentBuilder.build(enriched)
                self._pg.save_document(document)
                documents.append((enriched, document))
            if recreate is None:
                self._index_writer.index(documents, force=force, stats=stats)
            else:
                self._index_writer.rebuild(documents, recreate, stats)
            status = "partial" if stats.get("qdrant_failed") or stats.get("qdrant_delete_failed") else "succeeded"
        finally:
            self._pg.finish_run(run_id, status, stats.as_dict())
        return stats

    def _ingest(self, options: IngestOptions, stats: RunStats) -> None:
        self._enricher.start_run()
        self._index_writer.check_model(options.is_full_run)
        loaded = ZipLoader.load(options.input_path)
        stats.set("loaded", len(loaded.products))
        if loaded.errors:
            stats.set("load_errors", len(loaded.errors))

        raws = list(loaded.products)
        if options.only_products:
            wanted = set(options.only_products)
            raws = [raw for raw in raws if raw.id in wanted]
            missing = wanted - {raw.id for raw in raws}
            if missing:
                logger.warning("Requested products not found in input", extra=LogSetup.fields(ids=sorted(missing)))
        if options.limit is not None:
            raws = raws[: options.limit]
        stats.set("selected", len(raws))

        prepared = [ProductPreparer.prepare(raw) for raw in raws]
        stats.set("normalized", len(prepared))
        stats.set("needs_web_enrichment", sum(p.completeness.needs_web for p in prepared))

        states = self._pg.load_states()
        self._log_plan(prepared, states)
        # Already-enriched products first: they complete instantly, so progress reflects real work left.
        prepared.sort(key=lambda item: not self._has_llm_output(item, states))
        documents = self._enrich_and_record(prepared, states, options, stats)

        if options.is_full_run:
            self._deactivator.deactivate_missing(loaded, states, options.force, stats)
            self._deactivator.delete_inactive_from_index(stats)

        self._index_writer.index(documents, force=options.force, stats=stats)

    def _enrich_and_record(
        self,
        prepared: list[PreparedProduct],
        states: dict[str, ProductState],
        options: IngestOptions,
        stats: RunStats,
    ) -> list[tuple[EnrichedProduct, RetrievalDocument]]:
        """Enriches in worker threads and records each result on this thread as soon as it is done."""
        web_cache = self._pg.load_web_pages()
        policy = options.enrichment_policy
        documents: list[tuple[EnrichedProduct, RetrievalDocument]] = []
        self._progress.start("enrich", len(prepared))
        pool = ThreadPoolExecutor(max_workers=options.concurrency)
        try:
            futures = [
                pool.submit(self._enricher.enrich, item, states.get(item.product.id), web_cache, policy)
                for item in prepared
            ]
            for future in as_completed(futures):
                self._recorder.record(future.result(), stats, documents)
                self._progress.advance("enrich")
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)
            raise
        pool.shutdown()
        self._progress.finish("enrich")
        return documents

    def _log_plan(self, prepared: list[PreparedProduct], states: dict[str, ProductState]) -> None:
        done = sum(self._has_llm_output(item, states) for item in prepared)
        logger.info(
            "LLM enrichment plan",
            extra=LogSetup.fields(
                already_enriched=done,
                pending=len(prepared) - done,
                note="already enriched products are reused unless their input changed or --force is set",
            ),
        )

    @staticmethod
    def _has_llm_output(item: PreparedProduct, states: dict[str, ProductState]) -> bool:
        state = states.get(item.product.id)
        return state is not None and state.llm_output is not None
