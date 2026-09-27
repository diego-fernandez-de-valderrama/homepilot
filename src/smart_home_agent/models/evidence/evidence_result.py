from pydantic import BaseModel

from smart_home_agent.models.evidence.evidence import Evidence
from smart_home_agent.models.evidence.field_provenance import FieldProvenance


class EvidenceResult(BaseModel):
    product_id: str
    title: str
    topic: str
    items: list[Evidence]
    provenance: list[FieldProvenance]
    note: str | None = None
