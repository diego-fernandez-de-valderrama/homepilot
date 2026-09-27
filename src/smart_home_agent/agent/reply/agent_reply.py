from pydantic import BaseModel, Field

from smart_home_agent.agent.reply.turn_trace import TurnTrace
from smart_home_agent.guardrail.report import GuardrailReport
from smart_home_agent.models.cart import CartConfirmation
from smart_home_agent.models.profile import CustomerProfile
from smart_home_agent.models.rich import RichContent
from smart_home_agent.session import SessionState


class AgentReply(BaseModel):
    """Everything one turn produced, for the interface."""

    text: str
    detected_language: str | None  # heuristic language of the user message ("en" | "de" | None)
    trace: TurnTrace
    state: SessionState
    guardrail: GuardrailReport | None = None  # what the input/output guardrail decided this turn
    rich: RichContent | None = None  # catalog data for the presentation tags in `text` (None: no tags)
    # Cart changes waiting for the customer's decision in the interface (answered with AgentService.confirm).
    pending_confirmations: list[CartConfirmation] = Field(default_factory=list)
    profile: CustomerProfile | None = None  # stored customer facts as of the end of the turn (None: no memory)
    # Technical error of the turn (e.g. the model returned no content after all retries); for logs and the
    # developer panel only. The interface shows a friendly message when the turn produced nothing to show.
    error: str | None = None

    @property
    def failed(self) -> bool:
        """Nothing to show: no answer text and no cart change waiting for the customer."""
        return not self.text.strip() and not self.pending_confirmations
