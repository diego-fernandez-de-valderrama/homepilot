from dataclasses import dataclass

from catalog_ingestion.vocabulary import Dimension, FactSource, FactStatus


@dataclass(frozen=True, slots=True)
class CompatibilityClaim:
    dimension: Dimension
    value: str
    status: FactStatus
    source: FactSource
    evidence_quote: str
