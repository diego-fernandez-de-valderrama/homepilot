from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WebPage:
    url: str
    ok: bool
    method: str | None  # "http" or "gemini_url_context"
    http_status: int | None
    text: str
    error: str | None
    fetched_at: datetime
    transient: bool = False  # failure that may succeed later (quota, timeout): never cached
