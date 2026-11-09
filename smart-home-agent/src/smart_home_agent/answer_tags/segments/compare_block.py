from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompareBlock:
    ids: tuple[str, ...]
