from pydantic import BaseModel

from smart_home_agent.models.profile.fact_kind import FactKind


class NewFact(BaseModel):
    """A fact to store (before it has an id)."""

    kind: FactKind
    value: str
    canonical: str | None = None
    label: str
