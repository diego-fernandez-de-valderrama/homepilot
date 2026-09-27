"""The Gemini client shared by LLM enrichment, the url_context fetcher and the embedder (and the agent).

`GeminiClient` paces requests (private `_rate_limiter`, separate limits for generation and embeddings),
retries rate limits and server errors (`_retry_schedule`, honoring the server's retry delay) and turns a
per-day quota into `QuotaExhaustedError` (`_api_errors`). `TextGenerator` is the part of it the
enricher and the url_context fetcher depend on.
"""

from catalog_ingestion.core.gemini.gemini_cancelled_error import GeminiCancelledError
from catalog_ingestion.core.gemini.gemini_client import GeminiClient
from catalog_ingestion.core.gemini.gemini_model_not_found_error import GeminiModelNotFoundError
from catalog_ingestion.core.gemini.gemini_not_configured_error import GeminiNotConfiguredError
from catalog_ingestion.core.gemini.quota_exhausted_error import QuotaExhaustedError
from catalog_ingestion.core.gemini.text_generator import TextGenerator

__all__ = [
    "GeminiCancelledError",
    "GeminiClient",
    "GeminiModelNotFoundError",
    "GeminiNotConfiguredError",
    "QuotaExhaustedError",
    "TextGenerator",
]
