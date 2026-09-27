"""What the guardrail did in one turn. Kept apart from the callbacks, so the agent's reply model can use it
without importing the callbacks (which depend on the agent's state helpers)."""

from pydantic import BaseModel, Field

from smart_home_agent.guardrail.categories import GuardrailDecision
from smart_home_agent.guardrail.output_check import Violation
from smart_home_agent.guardrail.responses import ResponseType


class GuardrailReport(BaseModel):
    """What the guardrail did in one turn (developer panel and logs only)."""

    input: GuardrailDecision | None = None
    input_error: str | None = None  # embedding failed: the message was allowed (fail-open)
    output_violations: list[Violation] = Field(default_factory=list)
    response_type: ResponseType | None = None  # set when a deterministic reply was returned
