"""Customer memory rules, enforced in code (the prompt only asks the model to follow them):

- a fact is stored only with a verbatim quote (whole words) from the customer's current message, and each value
  must be stated in that quote or in another clause of the message that is not about someone else, so cart
  contents, tool results and the model's own guesses can never become facts;
- quotes whose clause is about other people (a friend, family, a gift, "sie hat ...") are rejected: only the
  customer's own facts are kept;
- ecosystems and voice assistants resolve to canonical ids (ambiguous input raises, as everywhere);
- hubs (bridges, gateways, access points, connectors) map to a canonical hub id only when that is safe,
  otherwise they keep the customer's wording. Owned hardware that maps to a hub is stored as a hub too, so
  the hubs are complete even when the model passes a bridge as an owned device.

`ProfileService.remember` runs them in order: `_evidence_check` (quote), `_fact_builder` (values), `_evidence_check`
(backed by the customer's words, `_third_party` clauses), `_retraction`, then the store.
"""

from smart_home_agent.services.profile.memory_rule_error import MemoryRuleError
from smart_home_agent.services.profile.profile_service import ProfileService

__all__ = ["MemoryRuleError", "ProfileService"]
