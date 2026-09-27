from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ItemsBlock:
    ids: tuple[str, ...]
