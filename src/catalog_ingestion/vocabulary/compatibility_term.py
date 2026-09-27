from dataclasses import dataclass

from catalog_ingestion.vocabulary.enums import Dimension


@dataclass(frozen=True, slots=True)
class CompatibilityTerm:
    canonical: str
    dimension: Dimension
    label: str
    aliases: tuple[str, ...]
