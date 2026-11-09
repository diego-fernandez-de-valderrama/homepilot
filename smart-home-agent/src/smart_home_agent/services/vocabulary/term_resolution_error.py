class TermResolutionError(ValueError):
    """The value maps to no canonical term, or to several (then `options` lists them)."""

    def __init__(self, kind: str, value: str, options: list[str] | None = None) -> None:
        self.kind = kind
        self.value = value
        self.options = options or []
        reason = f"ambiguous, could mean: {', '.join(self.options)}" if self.options else "not recognized"
        super().__init__(f"{kind} {value!r} is {reason}")
