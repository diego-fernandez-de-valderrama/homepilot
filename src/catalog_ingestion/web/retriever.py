"""Fetches a product page through a chain of fetchers, never raising."""

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime

from catalog_ingestion.core.logging import log_fields
from catalog_ingestion.domain.enrichment import WebPage
from catalog_ingestion.web.fetchers import Fetcher, FetchResult

logger = logging.getLogger(__name__)

# "ClientError: 404 NOT_FOUND ..." as recorded by `retrieve` for a fetcher that raised.
_EXCEPTION_ERROR = re.compile(r"^[A-Z]\w*(Error|Exception|Timeout): ")


class WebRetriever:
    def __init__(self, fetchers: Sequence[Fetcher]) -> None:
        self._fetchers = tuple(fetchers)

    @property
    def methods(self) -> tuple[str, ...]:
        return tuple(fetcher.method for fetcher in self._fetchers)

    def should_retry(self, cached: WebPage) -> bool:
        """A cached failure is retried when the chain now has a fetcher it never reached (e.g. the Gemini
        fallback after GEMINI_API_KEY was configured), or when its last error was an exception (API error,
        timeout): those say nothing about the page and are no longer cached, but older runs cached them."""
        if cached.ok or not self._fetchers:
            return False
        if cached.method != self._fetchers[-1].method:
            return True
        last_error = (cached.error or "").rsplit("; ", 1)[-1]
        return bool(_EXCEPTION_ERROR.match(last_error.split(": ", 1)[-1]))

    def retrieve(self, url: str) -> WebPage:
        errors: list[str] = []
        transient = False
        last: FetchResult | None = None
        for fetcher in self._fetchers:
            try:
                result = fetcher.fetch(url)
            except Exception as exc:
                result = FetchResult(
                    ok=False, method=fetcher.method, error=f"{type(exc).__name__}: {exc}", transient=True
                )
            last = result
            if result.ok:
                return WebPage(
                    url=url,
                    ok=True,
                    method=result.method,
                    http_status=result.http_status,
                    text=result.text,
                    error=None,
                    fetched_at=datetime.now(UTC),
                )
            errors.append(f"{result.method}: {result.error}")
            transient = transient or result.transient
            logger.info("Fetcher failed", extra=log_fields(url=url, method=result.method, error=result.error))

        return WebPage(
            url=url,
            ok=False,
            method=last.method if last else None,
            http_status=last.http_status if last else None,
            text="",
            error="; ".join(errors) or "no fetchers configured",
            fetched_at=datetime.now(UTC),
            transient=transient,
        )
