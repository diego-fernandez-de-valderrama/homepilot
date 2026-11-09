import httpx

from catalog_ingestion.core import WebSettings
from catalog_ingestion.enrichment.web._html_text import HtmlText
from catalog_ingestion.enrichment.web.fetch_result import FetchResult


class HttpxFetcher:
    """Plain HTTP GET. bauhaus.info currently answers 403 (bot protection) to this."""

    method = "http"
    MIN_USEFUL_CHARS = 200

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
        if response.history and self._path(str(response.url)) != self._path(url):
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
        text = HtmlText.to_text(response.text, self._settings.max_text_chars)
        if len(text) < self.MIN_USEFUL_CHARS:
            return FetchResult(ok=False, method=self.method, http_status=200, error="page has no usable text")
        return FetchResult(ok=True, method=self.method, http_status=200, text=text)

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _path(url: str) -> str:
        return httpx.URL(url).path.rstrip("/")
