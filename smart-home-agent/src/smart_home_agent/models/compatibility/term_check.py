from catalog_ingestion.vocabulary import Dimension, FactStatus
from pydantic import BaseModel

from smart_home_agent.models.evidence import Evidence


class TermCheck(BaseModel):
    term: str  # canonical id
    label: str
    dimension: Dimension
    status: FactStatus
    evidence: list[Evidence]
    notes: list[str]
