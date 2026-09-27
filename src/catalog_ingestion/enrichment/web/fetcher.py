from typing import Protocol

from catalog_ingestion.enrichment.web.fetch_result import FetchResult


class Fetcher(Protocol):
    """Reads exactly the URL it is given: no crawling, no search."""

    method: str

    def fetch(self, url: str) -> FetchResult: ...
