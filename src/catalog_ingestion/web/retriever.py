"""Fetches a product page through a chain of fetchers, never raising."""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from catalog_ingestion.core.logging import log_fields
from catalog_ingestion.domain.enrichment import WebPage
from catalog_ingestion.web.fetchers import Fetcher, FetchResult

logger = logging.getLogger(__name__)


class WebRetriever:
    def __init__(self, fetchers: Sequence[Fetcher]) -> None:
        self._fetchers = tuple(fetchers)

    @property
    def methods(self) -> tuple[str, ...]:
        return tuple(fetcher.method for fetcher in self._fetchers)

    def should_retry(self, cached: WebPage) -> bool:
        """A cached failure is retried when the chain now has a fetcher it never reached
        (e.g. the Gemini fallback after GEMINI_API_KEY was configured)."""
        return not cached.ok and bool(self._fetchers) and cached.method != self._fetchers[-1].method

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
