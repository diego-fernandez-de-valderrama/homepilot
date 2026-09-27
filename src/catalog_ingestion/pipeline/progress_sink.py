from typing import Protocol


class ProgressSink(Protocol):
    """Where the pipeline reports progress per stage ("enrich", "embed")."""

    def start(self, stage: str, total: int) -> None: ...

    def advance(self, stage: str, amount: int = 1) -> None: ...

    def finish(self, stage: str) -> None: ...
