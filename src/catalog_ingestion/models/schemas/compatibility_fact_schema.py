from pydantic import BaseModel, Field

from catalog_ingestion.models.schemas.evidence_schema import EvidenceSchema
from catalog_ingestion.vocabulary import Dimension, FactStatus, Method


class CompatibilityFactSchema(BaseModel):
    dimension: Dimension
    raw_value: str
    canonical_value: str | None
    label: str | None = None
    status: FactStatus
    evidence: EvidenceSchema
    confidence: float = Field(ge=0.0, le=1.0)
    method: Method
