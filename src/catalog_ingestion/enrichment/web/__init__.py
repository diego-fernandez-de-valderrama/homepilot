"""The product page for enrichment: `WebRetriever` runs a chain of `Fetcher`s and returns a `WebPage`.

- `HttpxFetcher`: plain GET, HTML -> text (private `_html_text`); bauhaus.info answers 403 to it.
- `GeminiUrlContextFetcher`: the fallback through Gemini's url_context tool; only accepted when Gemini
  reports a successful retrieval of this exact URL.

Each fetcher reads exactly the URL it is given (no crawling, no search) and reports a `FetchResult`;
`transient` failures (timeouts, quota) are never cached.
"""

from catalog_ingestion.enrichment.web.fetch_result import FetchResult
from catalog_ingestion.enrichment.web.fetcher import Fetcher
from catalog_ingestion.enrichment.web.gemini_url_context_fetcher import GeminiUrlContextFetcher
from catalog_ingestion.enrichment.web.httpx_fetcher import HttpxFetcher
from catalog_ingestion.enrichment.web.web_retriever import WebRetriever

__all__ = ["FetchResult", "Fetcher", "GeminiUrlContextFetcher", "HttpxFetcher", "WebRetriever"]
