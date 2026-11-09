from pydantic import BaseModel, Field

from smart_home_agent.models.profile.customer_fact import CustomerFact
from smart_home_agent.models.profile.customer_profile import CustomerProfile
from smart_home_agent.models.profile.rejected_fact import RejectedFact


class ProfileUpdate(BaseModel):
    added: list[CustomerFact] = Field(default_factory=list)
    retracted: list[CustomerFact] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)  # values that were already stored
    rejected: list[RejectedFact] = Field(default_factory=list)
    profile: CustomerProfile
