from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
import streamlit as st

from smart_home_agent.models import Product
from smart_home_agent.ui.components import ProductCardHtml

_GONE = frozenset({404, 410})
_TIMEOUT_SECONDS = 3
_MAX_WORKERS = 8


class ImageAvailability:
    """Which product image URLs are gone (about 4% of the catalog's CDN links return 404 in the source data).

    `st.html` strips JavaScript, so a broken <img> cannot remove itself in the browser; the UI asks here
    first. Only a definite 404/410 counts as gone: timeouts and network errors keep the image (the browser may
    still load it). Results are cached, so re-rendering the history makes no request.
    """

    @staticmethod
    def missing_for(products: list[Product]) -> frozenset[str]:
        """The gone image URLs among the ones these products' components would load."""
        return ImageAvailability.missing(ProductCardHtml.image_urls(products))

    @staticmethod
    @st.cache_data(ttl=timedelta(days=1), show_spinner=False)
    def missing(urls: tuple[str, ...]) -> frozenset[str]:
        return ImageAvailability.find_missing(urls)

    @staticmethod
    def find_missing(urls: tuple[str, ...]) -> frozenset[str]:
        if not urls:
            return frozenset()
        with (
            httpx.Client(timeout=_TIMEOUT_SECONDS, headers={"User-Agent": "Mozilla/5.0 HomePilot"}) as client,
            ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(urls))) as pool,
        ):
            gone = list(pool.map(lambda url: ImageAvailability._is_gone(client, url), urls))
        return frozenset(url for url, is_gone in zip(urls, gone, strict=True) if is_gone)

    @staticmethod
    def _is_gone(client: httpx.Client, url: str) -> bool:
        try:
            return client.head(url, follow_redirects=True).status_code in _GONE
        except httpx.HTTPError:
            return False
