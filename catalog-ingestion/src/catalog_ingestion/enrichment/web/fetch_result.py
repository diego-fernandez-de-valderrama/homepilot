from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FetchResult:
    ok: bool
    method: str
    text: str = ""
    http_status: int | None = None
    error: str | None = None
    transient: bool = False  # e.g. timeout, 429/5xx, Gemini quota: worth retrying in a later run
