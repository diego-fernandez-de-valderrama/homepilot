from catalog_ingestion.domain.enums import Dimension, FactStatus
from pydantic import BaseModel

from smart_home_agent.models.evidence import Evidence


class CompatibilityFact(BaseModel):
    dimension: Dimension
    canonical_value: str | None  # None when the raw value has no safe canonical mapping
    label: str | None
    raw_value: str
    status: FactStatus
    evidence: Evidence
