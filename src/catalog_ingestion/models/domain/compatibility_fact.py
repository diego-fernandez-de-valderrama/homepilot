from dataclasses import dataclass

from catalog_ingestion.models.domain.evidence import Evidence
from catalog_ingestion.vocabulary import Dimension, FactStatus, Method


@dataclass(frozen=True, slots=True)
class CompatibilityFact:
    dimension: Dimension
    raw_value: str
    canonical_value: str | None  # None when the raw value has no safe canonical mapping
    status: FactStatus
    evidence: Evidence
    confidence: float
    method: Method

    @property
    def key(self) -> tuple[Dimension, str]:
        return self.dimension, self.canonical_value or self.raw_value.casefold()
