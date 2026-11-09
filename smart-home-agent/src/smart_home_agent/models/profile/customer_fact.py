from datetime import datetime

from pydantic import BaseModel

from smart_home_agent.models.profile.fact_kind import FactKind


class CustomerFact(BaseModel):
    id: int
    user_id: str
    kind: FactKind
    value: str  # canonical id when `canonical` is set, else the normalized customer wording
    canonical: str | None = None  # None = no safe mapping to the vocabulary
    label: str  # the customer's own wording
    evidence: str  # verbatim quote from the customer's message
    session_id: str | None = None
    created_at: datetime
    active: bool = True
    retracted_at: datetime | None = None
    retracted_evidence: str | None = None
