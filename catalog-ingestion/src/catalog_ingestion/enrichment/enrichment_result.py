from dataclasses import dataclass
from typing import Any

from catalog_ingestion.models import EnrichedProduct, WebPage
from catalog_ingestion.preparation import PreparedProduct


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    """One product after enrichment, ready to be persisted (`enriched` is None when it failed)."""

    prepared: PreparedProduct
    enriched: EnrichedProduct | None
    fetched_page: WebPage | None  # newly fetched page to cache
    llm_output: dict[str, Any] | None
    enrichment_hash: str | None
    llm_status: str  # called | cached | skipped | skipped_quota | failed
    error: str | None = None
    kept_previous_llm: bool = False  # no new result: the stored output was kept
