from pydantic import BaseModel, Field

from catalog_ingestion.models.schemas.evidence_schema import EvidenceSchema
from catalog_ingestion.vocabulary import Method, Necessity, RequirementKind


class RequirementSchema(BaseModel):
    item: str
    canonical_item: str | None
    kind: RequirementKind
    necessity: Necessity
    alternatives: list[str]
    evidence: EvidenceSchema
    confidence: float = Field(ge=0.0, le=1.0)
    method: Method
