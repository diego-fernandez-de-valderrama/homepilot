"""Deterministic replies for blocked messages and failed output checks (no model call).

text = pick_response(ResponseType.ELECTRICAL, "de", previous=last_reply)
"""

from smart_home_agent.guardrail.replies.picker import pick_response
from smart_home_agent.guardrail.replies.pools import RESPONSES
from smart_home_agent.guardrail.replies.response_type import ResponseType

__all__ = ["RESPONSES", "ResponseType", "pick_response"]
