from catalog_ingestion.vocabulary import Necessity, RequirementKind
from pydantic import BaseModel

from smart_home_agent.models.evidence import Evidence


class ProductRequirement(BaseModel):
    item: str
    canonical_item: str | None
    label: str
    kind: RequirementKind
    necessity: Necessity
    alternatives: list[str]  # canonical ids; any one of them satisfies the requirement
    evidence: Evidence
