from dataclasses import dataclass

from catalog_ingestion.domain.enums import Dimension


@dataclass(frozen=True, slots=True)
class ResolvedTerm:
    canonical: str
    dimension: Dimension
    label: str
