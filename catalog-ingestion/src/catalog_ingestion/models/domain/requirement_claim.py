from dataclasses import dataclass

from catalog_ingestion.vocabulary import FactSource, Necessity, RequirementKind


@dataclass(frozen=True, slots=True)
class RequirementClaim:
    item: str
    kind: RequirementKind
    necessity: Necessity
    alternatives: tuple[str, ...]
    source: FactSource
    evidence_quote: str
