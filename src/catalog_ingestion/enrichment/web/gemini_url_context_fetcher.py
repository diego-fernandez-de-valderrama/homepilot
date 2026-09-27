from google.genai import types

from catalog_ingestion.core import TextGenerator, WebSettings
from catalog_ingestion.enrichment.web.fetch_result import FetchResult


class GeminiUrlContextFetcher:
    """Reads the page through Gemini's URL context tool (fetched by Google's infrastructure).

    The result is only accepted when Gemini reports a successful retrieval of this exact URL,
    so text generated from prior knowledge is never mistaken for page content.
    """

    method = "gemini_url_context"
    MIN_USEFUL_CHARS = 200

    PROMPT = """Open this product page with the URL context tool: {url}

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

    def __init__(self, client: TextGenerator, settings: WebSettings) -> None:
        self._client = client
        self._settings = settings

    def fetch(self, url: str) -> FetchResult:
        try:
            response = self._client.generate(
                self.PROMPT.format(url=url),
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
            definitive = bool(statuses) and statuses[0] not in self._INCONCLUSIVE_STATUSES
            return FetchResult(
                ok=False, method=self.method, error=f"url_context retrieval failed: {status}", transient=not definitive
            )

        text = (response.text or "").strip()
        if not text or text.startswith("NO_CONTENT") or len(text) < self.MIN_USEFUL_CHARS:
            return FetchResult(ok=False, method=self.method, error="url_context returned no product content")
        return FetchResult(ok=True, method=self.method, text=text[: self._settings.max_text_chars])
