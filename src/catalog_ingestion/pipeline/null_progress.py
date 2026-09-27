class NullProgress:
    """A `ProgressSink` that reports nothing."""

    def start(self, stage: str, total: int) -> None:
        pass

    def advance(self, stage: str, amount: int = 1) -> None:
        pass

    def finish(self, stage: str) -> None:
        pass
