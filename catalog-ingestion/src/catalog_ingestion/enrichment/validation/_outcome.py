from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Outcome[T]:
    """A checked claim: the accepted value (None when dropped) and a validation note."""

    value: T | None
    note: str | None = None
