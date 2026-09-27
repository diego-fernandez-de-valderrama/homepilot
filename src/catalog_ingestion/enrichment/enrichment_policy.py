from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnrichmentPolicy:
    """What one run may do per product (from the `ingest` options)."""

    force: bool = False  # ignore the cached LLM output
    skip_web: bool = False  # never fetch (cached pages are still used)
    skip_llm: bool = False  # never call the LLM (stored output is kept)
    refresh_web: bool = False  # re-fetch cached pages
