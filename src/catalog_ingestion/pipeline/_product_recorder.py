import logging

from catalog_ingestion.core import LogSetup
from catalog_ingestion.database import PostgresRepository, UpsertOutcome
from catalog_ingestion.enrichment import EnrichmentResult
from catalog_ingestion.indexing import RetrievalDocumentBuilder
from catalog_ingestion.models import EnrichedProduct, RetrievalDocument
from catalog_ingestion.pipeline.run_stats import RunStats
from catalog_ingestion.vocabulary import WebStatus

logger = logging.getLogger(__name__)


class ProductRecorder:
    """Main thread: persists one enrichment result (web page cache, product, retrieval document) and counts it."""

    def __init__(self, postgres: PostgresRepository) -> None:
        self._pg = postgres

    def record(
        self,
        result: EnrichmentResult,
        stats: RunStats,
        documents: list[tuple[EnrichedProduct, RetrievalDocument]],
    ) -> None:
        """Appends the product and its retrieval document to `documents` (to be indexed) when it was stored."""
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
        if result.kept_previous_llm:
            stats.inc("llm_kept_previous")
        stats.inc("validated")
        if enriched.validation_notes:
            stats.inc("validation_notes", len(enriched.validation_notes))

        try:
            outcome = self._pg.upsert_product(
                enriched, result.prepared.raw, result.prepared.raw_hash, result.enrichment_hash, result.llm_output
            )
            stats.inc(f"postgres_{outcome.value}")
            if outcome is not UpsertOutcome.UNCHANGED:
                stats.inc("postgres_upserted")
            document = RetrievalDocumentBuilder.build(enriched)
            self._pg.save_document(document)
        except Exception:
            logger.exception("Storing the product failed", extra=LogSetup.fields(product_id=product_id))
            stats.inc("failed")
            return
        documents.append((enriched, document))
