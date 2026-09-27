from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Spec:
    name: str
    value: str
    unit: str | None
