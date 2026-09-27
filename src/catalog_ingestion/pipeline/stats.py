"""Run counters and the progress interface the pipeline reports to."""

from collections import Counter
from typing import Protocol

# Display order of the summary; counters not listed here are appended at the end.
ORDER: tuple[str, ...] = (
    "loaded", "load_errors", "selected", "normalized", "needs_web_enrichment", "web_fetched",
    "web_enrichment_successful", "web_enrichment_failed", "web_enrichment_skipped",
    "web_transient_failures_not_cached",
    "llm_called", "llm_cached", "llm_skipped", "llm_skipped_quota", "llm_failed", "llm_kept_previous",
    "validated", "validation_notes", "failed",
    "loaded_from_postgres", "postgres_inserted", "postgres_updated", "postgres_unchanged", "postgres_upserted",
    "postgres_deactivated", "deactivation_skipped", "deactivation_refused",
    "qdrant_indexed", "qdrant_unchanged", "qdrant_failed", "qdrant_deleted_inactive", "qdrant_delete_failed",
    "qdrant_skipped_no_embedder",
)  # fmt: skip


class RunStats:
    """Named counters for one run."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def inc(self, name: str, amount: int = 1) -> None:
        self._counts[name] += amount

    def set(self, name: str, value: int) -> None:
        self._counts[name] = value

    def get(self, name: str) -> int:
        return self._counts.get(name, 0)

    def as_dict(self) -> dict[str, int]:
        known = [name for name in ORDER if name in self._counts]
        extra = sorted(name for name in self._counts if name not in ORDER)
        return {name: self._counts[name] for name in (*known, *extra)}


class ProgressSink(Protocol):
    def start(self, stage: str, total: int) -> None: ...

    def advance(self, stage: str, amount: int = 1) -> None: ...

    def finish(self, stage: str) -> None: ...


class NullProgress:
    def start(self, stage: str, total: int) -> None:
        pass

    def advance(self, stage: str, amount: int = 1) -> None:
        pass

    def finish(self, stage: str) -> None:
        pass
