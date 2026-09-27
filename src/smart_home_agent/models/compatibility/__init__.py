"""Compatibility check results. `unknown` is a real state, never a default for supported/unsupported.

`CompatibilityResult` is the result for one product: a `TermCheck` per requested term, a `RequirementCheck`
per catalog requirement, and `AccessorySuggestion`s for required hubs the customer may not own yet.
"""

from smart_home_agent.models.compatibility.accessory_suggestion import AccessorySuggestion
from smart_home_agent.models.compatibility.compatibility_result import CompatibilityResult
from smart_home_agent.models.compatibility.requirement_check import RequirementCheck
from smart_home_agent.models.compatibility.term_check import TermCheck
from smart_home_agent.models.compatibility.types import RequirementStatus

__all__ = ["AccessorySuggestion", "CompatibilityResult", "RequirementCheck", "RequirementStatus", "TermCheck"]
