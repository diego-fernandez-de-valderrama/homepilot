"""Page fetchers. Each one reads exactly the URL it is given: no crawling, no search."""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx
from google.genai import types

from catalog_ingestion.core.settings import WebSettings
from catalog_ingestion.llm.client import TextGenerator
from catalog_ingestion.web.html_text import html_to_text

logger = logging.getLogger(__name__)

_MIN_USEFUL_CHARS = 200


@dataclass(frozen=True, slots=True)
class FetchResult:
    ok: bool
    method: str
    text: str = ""
    http_status: int | None = None
    error: str | None = None
    transient: bool = False  # e.g. timeout, 429/5xx, Gemini quota: worth retrying in a later run


class Fetcher(Protocol):
    method: str

    def fetch(self, url: str) -> FetchResult: ...


def _path(url: str) -> str:
    return httpx.URL(url).path.rstrip("/")


class HttpxFetcher:
    """Plain HTTP GET. bauhaus.info currently answers 403 (bot protection) to this."""

    method = "http"

    def __init__(self, settings: WebSettings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            },
        )

    def fetch(self, url: str) -> FetchResult:
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            return FetchResult(ok=False, method=self.method, error=f"{type(exc).__name__}: {exc}", transient=True)
        if response.history and _path(str(response.url)) != _path(url):
            # A discontinued product usually redirects to a category page: that text is not this product.
            return FetchResult(
                ok=False,
                method=self.method,
                http_status=response.status_code,
                error=f"redirected to another page: {response.url}",
            )
        if response.status_code != 200:
            return FetchResult(
                ok=False,
                method=self.method,
                http_status=response.status_code,
                error=f"HTTP {response.status_code}",
                transient=response.status_code == 429 or response.status_code >= 500,
            )
        text = html_to_text(response.text, self._settings.max_text_chars)
        if len(text) < _MIN_USEFUL_CHARS:
            return FetchResult(ok=False, method=self.method, http_status=200, error="page has no usable text")
        return FetchResult(ok=True, method=self.method, http_status=200, text=text)

    def close(self) -> None:
        self._client.close()


_URL_CONTEXT_PROMPT = """Open this product page with the URL context tool: {url}

Copy the product information that is visible on that page, as plain text:
- product name
- product description
- all technical specifications as "Key: Value" lines
- compatibility, system requirements and notes

Rules:
- Copy the text as written on the page (keep the original language). Do not summarize or translate.
- Do not add anything that is not on the page. Do not use prior knowledge.
- If the page cannot be opened or shows no product information, answer exactly: NO_CONTENT
"""


_INCONCLUSIVE_STATUSES = frozenset({types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_UNSPECIFIED})


class GeminiUrlContextFetcher:
    """Reads the page through Gemini's URL context tool (fetched by Google's infrastructure).

    The result is only accepted when Gemini reports a successful retrieval of this exact URL,
    so text generated from prior knowledge is never mistaken for page content.
    """

    method = "gemini_url_context"

    def __init__(self, client: TextGenerator, settings: WebSettings) -> None:
        self._client = client
        self._settings = settings

    def fetch(self, url: str) -> FetchResult:
        try:
            response = self._client.generate(
                _URL_CONTEXT_PROMPT.format(url=url),
                types.GenerateContentConfig(tools=[types.Tool(url_context=types.UrlContext())], temperature=0.0),
            )
        except Exception as exc:
            # Quota, rate limit or server errors say nothing about the page: retry in a later run.
            return FetchResult(ok=False, method=self.method, error=f"{type(exc).__name__}: {exc}", transient=True)

        candidate = response.candidates[0] if response.candidates else None
        metadata = candidate.url_context_metadata if candidate else None
        statuses = [
            entry.url_retrieval_status
            for entry in (metadata.url_metadata or [] if metadata else [])
            if entry.url_retrieval_status is not None
            and entry.retrieved_url
            and entry.retrieved_url.rstrip("/") == url.rstrip("/")
        ]
        if types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS not in statuses:
            status = statuses[0].value if statuses else "no_retrieval_metadata"
            # Only a definitive answer about the page is cached; the model not calling the tool at all
            # (no metadata) or an unspecified status says nothing about the page, so it is retried later.
            definitive = bool(statuses) and statuses[0] not in _INCONCLUSIVE_STATUSES
            return FetchResult(
                ok=False, method=self.method, error=f"url_context retrieval failed: {status}", transient=not definitive
            )

        text = (response.text or "").strip()
        if not text or text.startswith("NO_CONTENT") or len(text) < _MIN_USEFUL_CHARS:
            return FetchResult(ok=False, method=self.method, error="url_context returned no product content")
        return FetchResult(ok=True, method=self.method, text=text[: self._settings.max_text_chars])
