import httpx
from google.genai import types

from catalog_ingestion.core.settings import WebSettings
from catalog_ingestion.web.fetchers import FetchResult, GeminiUrlContextFetcher, HttpxFetcher
from catalog_ingestion.web.html_text import html_to_text
from catalog_ingestion.web.retriever import WebRetriever

URL = "https://www.bauhaus.info/led-lampen/x/p/1"
PAGE = (
    """<html><head><script type="application/ld+json">
{"@type": "Product", "name": "Lampe X", "description": "Funktioniert mit Matter.", "brand": {"name": "ACME"}}
</script><style>.x{}</style></head><body><nav>Menu</nav><main><h1>Lampe X</h1>
<p>Technische Daten</p><p>Datenübertragung: WLAN</p>"""
    + "<p>Mehr Text.</p>" * 40
    + "</main></body></html>"
)


class StaticFetcher:
    def __init__(self, method: str, result: FetchResult | Exception):
        self.method = method
        self._result = result
        self.calls = 0

    def fetch(self, url: str) -> FetchResult:
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_html_to_text_keeps_product_content_and_json_ld():
    text = html_to_text(PAGE, max_chars=10_000)
    assert "Funktioniert mit Matter." in text
    assert "Brand: ACME" in text
    assert "Datenübertragung: WLAN" in text
    assert "Menu" not in text and ".x{}" not in text


def test_httpx_fetcher_handles_status_codes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403) if "blocked" in request.url.path else httpx.Response(200, text=PAGE)

    fetcher = HttpxFetcher(WebSettings(), client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert fetcher.fetch(URL).ok
    blocked = fetcher.fetch("https://www.bauhaus.info/blocked")
    assert not blocked.ok and blocked.http_status == 403


def test_httpx_fetcher_handles_timeouts():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    result = HttpxFetcher(WebSettings(), client=httpx.Client(transport=httpx.MockTransport(handler))).fetch(URL)
    assert not result.ok and "ConnectTimeout" in (result.error or "")


def test_retriever_falls_back_and_never_raises():
    first = StaticFetcher("http", FetchResult(ok=False, method="http", http_status=403, error="HTTP 403"))
    second = StaticFetcher("gemini_url_context", FetchResult(ok=True, method="gemini_url_context", text="page"))
    page = WebRetriever([first, second]).retrieve(URL)
    assert page.ok and page.method == "gemini_url_context" and page.text == "page"

    broken = StaticFetcher("http", RuntimeError("boom"))
    page = WebRetriever([broken]).retrieve(URL)
    assert not page.ok and "boom" in (page.error or "")


def test_cached_failure_is_retried_only_when_a_new_fetcher_is_available():
    http = StaticFetcher("http", FetchResult(ok=False, method="http"))
    gemini = StaticFetcher("gemini_url_context", FetchResult(ok=False, method="gemini_url_context"))
    failed_http_only = WebRetriever([http]).retrieve(URL)
    assert not WebRetriever([http]).should_retry(failed_http_only)
    assert WebRetriever([http, gemini]).should_retry(failed_http_only)


def _gemini_response(text: str, status: types.UrlRetrievalStatus | None) -> types.GenerateContentResponse:
    metadata = (
        types.UrlContextMetadata(url_metadata=[types.UrlMetadata(retrieved_url=URL, url_retrieval_status=status)])
        if status
        else None
    )
    candidate = types.Candidate(
        content=types.Content(role="model", parts=[types.Part(text=text)]), url_context_metadata=metadata
    )
    return types.GenerateContentResponse(candidates=[candidate])


class FakeGenerator:
    model = "fake-model"

    def __init__(self, response: types.GenerateContentResponse) -> None:
        self._response = response

    def generate(self, contents: str, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        return self._response


def _fetch(status: types.UrlRetrievalStatus | None) -> FetchResult:
    page_text = "Lampe X\n" + "Datenübertragung: WLAN\n" * 20
    return GeminiUrlContextFetcher(FakeGenerator(_gemini_response(page_text, status)), WebSettings()).fetch(URL)


def test_url_context_requires_successful_retrieval_metadata():
    assert _fetch(types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS).ok
    # Text without retrieval metadata could come from the model's prior knowledge: rejected.
    assert not _fetch(None).ok
    assert not _fetch(types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_ERROR).ok
