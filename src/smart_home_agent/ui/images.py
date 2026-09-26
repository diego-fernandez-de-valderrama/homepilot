"""Which product image URLs are gone (about 4% of the catalog's CDN links return 404 in the source data).

`st.html` strips JavaScript, so a broken <img> cannot swap in a placeholder in the browser; the UI asks here
first. Only a definite 404/410 counts as gone: timeouts and network errors keep the image (the browser may
still load it). Results are cached, so re-rendering the history makes no request.
"""

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import streamlit as st

_GONE = frozenset({404, 410})
_TIMEOUT_SECONDS = 3
_MAX_WORKERS = 8


def _is_gone(url: str) -> bool:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 HomePilot"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS):
            return False
    except urllib.error.HTTPError as exc:
        return exc.code in _GONE
    except OSError:
        return False


@st.cache_data(ttl=timedelta(days=1), show_spinner=False)
def missing_images(urls: tuple[str, ...]) -> frozenset[str]:
    if not urls:
        return frozenset()
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(urls))) as pool:
        gone = pool.map(_is_gone, urls)
    return frozenset(url for url, is_gone in zip(urls, gone, strict=True) if is_gone)
