"""Which deterministic reply replaces a rejected answer."""

from smart_home_agent.guardrail.output import Violation
from smart_home_agent.guardrail.replies import ResponseType

# By the most severe violation the answer contains.
_FALLBACKS = (
    ("electrical", ResponseType.ELECTRICAL),
    ("prompt_leak", ResponseType.PROMPT_INJECTION),
    ("off_topic", ResponseType.OFF_TOPIC),
)


def fallback_type(violations: list[Violation]) -> ResponseType:
    kinds = {v.kind for v in violations}
    return next((response for kind, response in _FALLBACKS if kind in kinds), ResponseType.OUTPUT_FALLBACK)
