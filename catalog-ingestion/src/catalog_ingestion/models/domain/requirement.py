from dataclasses import dataclass

from catalog_ingestion.models.domain.evidence import Evidence
from catalog_ingestion.vocabulary import Method, Necessity, RequirementKind


@dataclass(frozen=True, slots=True)
class Requirement:
    item: str
    canonical_item: str | None
    kind: RequirementKind
    necessity: Necessity
    alternatives: tuple[str, ...]  # canonical ids; any one of them satisfies the requirement
    evidence: Evidence
    confidence: float
    method: Method

    @property
    def key(self) -> str:
        return self.canonical_item or self.item.casefold()
