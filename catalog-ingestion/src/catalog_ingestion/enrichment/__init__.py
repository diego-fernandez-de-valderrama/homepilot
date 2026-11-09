"""Stage 2, external I/O: `PreparedProduct` -> validated `EnrichedProduct`. Import everything from here:

    from catalog_ingestion.enrichment import ProductEnricher, Validator, LLMEnricher, WebRetriever, ...

`ProductEnricher.enrich` runs per product in a worker thread (no database access):

1. `web/`: when the catalog entry is incomplete (`needs_web`), the product page through `WebRetriever`
   (`HttpxFetcher`, then `GeminiUrlContextFetcher`); cached pages are reused, a failed refresh never replaces
   a good cached page.
2. `llm/`: the stored LLM output is reused while its `EnrichmentKey` is unchanged (older key formats are still
   accepted), otherwise `LLMEnricher` calls Gemini with the `PromptBuilder` prompt. When no new result is
   possible (`--skip-llm`, quota, failure) the stored output is kept under its old key, so the product is
   re-enriched later.
3. `validation/`: `Validator` checks every LLM claim against the sources; the catalog wins.

The `EnrichmentPolicy` holds the run's flags; the outcome is an `EnrichmentResult`.
"""

from catalog_ingestion.enrichment.enrichment_key import EnrichmentKey
from catalog_ingestion.enrichment.enrichment_policy import EnrichmentPolicy
from catalog_ingestion.enrichment.enrichment_result import EnrichmentResult
from catalog_ingestion.enrichment.llm import Enricher, LLMEnricher, LLMResult, PromptBuilder
from catalog_ingestion.enrichment.product_enricher import ProductEnricher
from catalog_ingestion.enrichment.validation import Validator
from catalog_ingestion.enrichment.web import (
    Fetcher,
    FetchResult,
    GeminiUrlContextFetcher,
    HttpxFetcher,
    WebRetriever,
)

__all__ = [
    "Enricher",
    "EnrichmentKey",
    "EnrichmentPolicy",
    "EnrichmentResult",
    "FetchResult",
    "Fetcher",
    "GeminiUrlContextFetcher",
    "HttpxFetcher",
    "LLMEnricher",
    "LLMResult",
    "ProductEnricher",
    "PromptBuilder",
    "Validator",
    "WebRetriever",
]
