from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Category:
    key: str
    label_en: str
    label_de: str
    slugs: tuple[str, ...]
