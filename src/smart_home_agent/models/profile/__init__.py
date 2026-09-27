"""Customer memory: facts a customer stated about themself, kept per user id across conversations.

A `NewFact` is stored as a `CustomerFact`; a customer's facts form their `CustomerProfile` (rendered for the
system instruction by `prompt_lines`). A remember/forget call returns a `ProfileUpdate` (with `RejectedFact`s
for values the message did not state). `CustomerSummary` lists stored customers for the interface.
"""

from smart_home_agent.models.profile.customer_fact import CustomerFact
from smart_home_agent.models.profile.customer_profile import CustomerProfile
from smart_home_agent.models.profile.customer_summary import CustomerSummary
from smart_home_agent.models.profile.fact_kind import FactKind
from smart_home_agent.models.profile.new_fact import NewFact
from smart_home_agent.models.profile.profile_update import ProfileUpdate
from smart_home_agent.models.profile.rejected_fact import RejectedFact

__all__ = [
    "CustomerFact",
    "CustomerProfile",
    "CustomerSummary",
    "FactKind",
    "NewFact",
    "ProfileUpdate",
    "RejectedFact",
]
