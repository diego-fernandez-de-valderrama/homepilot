from pydantic import BaseModel

from smart_home_agent.models.profile.fact_kind import FactKind


class RejectedFact(BaseModel):
    kind: FactKind | None = None
    value: str | None = None
    reason: str
