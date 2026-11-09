import dataclasses
from datetime import UTC, datetime

import httpx
from google.genai import types

from catalog_ingestion.core import WebSettings
from catalog_ingestion.enrichment import FetchResult, GeminiUrlContextFetcher, HttpxFetcher, WebRetriever
from catalog_ingestion.enrichment.web._html_text import HtmlText
from catalog_ingestion.models import WebPage

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
    text = HtmlText.to_text(PAGE, max_chars=10_000)
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


def test_url_context_without_retrieval_metadata_is_transient():
    assert _fetch(None).transient  # the model did not open the page: retried in a later run
    assert not _fetch(types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_ERROR).transient


def test_httpx_fetcher_rejects_a_redirect_to_another_page():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/p/1"):
            return httpx.Response(301, headers={"Location": "https://www.bauhaus.info/led-lampen/c/10000"})
        return httpx.Response(200, text=PAGE)

    fetcher = HttpxFetcher(
        WebSettings(), client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    )
    result = fetcher.fetch(URL)
    assert not result.ok and "redirected" in (result.error or "")

    def to_https(request: httpx.Request) -> httpx.Response:
        if request.url.scheme == "http":
            return httpx.Response(301, headers={"Location": str(request.url.copy_with(scheme="https"))})
        return httpx.Response(200, text=PAGE)

    same_page = HttpxFetcher(
        WebSettings(), client=httpx.Client(transport=httpx.MockTransport(to_https), follow_redirects=True)
    )
    assert same_page.fetch(URL.replace("https://", "http://")).ok


def test_cached_api_errors_of_the_last_fetcher_are_retried():
    http = StaticFetcher("http", FetchResult(ok=False, method="http", http_status=403, error="HTTP 403"))
    gemini = StaticFetcher("gemini_url_context", RuntimeError("placeholder"))
    retriever = WebRetriever([http, gemini])
    api_error = WebPage(
        URL, False, "gemini_url_context", None, "",
        "http: HTTP 403; gemini_url_context: ClientError: 404 NOT_FOUND. {'error': ...}",
        datetime(2026, 9, 26, tzinfo=UTC),
    )  # fmt: skip
    definitive = dataclasses.replace(
        api_error, error="http: HTTP 403; gemini_url_context: url_context retrieval failed: URL_RETRIEVAL_STATUS_ERROR"
    )
    assert retriever.should_retry(api_error)
    assert not retriever.should_retry(definitive)
