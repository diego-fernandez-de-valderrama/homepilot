from catalog_ingestion.vocabulary import Necessity, RequirementKind
from pydantic import BaseModel

from smart_home_agent.models.compatibility.types import RequirementStatus
from smart_home_agent.models.evidence import Evidence


class RequirementCheck(BaseModel):
    label: str
    canonical_item: str | None
    kind: RequirementKind
    necessity: Necessity
    alternatives: list[str]  # human-readable labels
    status: RequirementStatus
    evidence: Evidence
