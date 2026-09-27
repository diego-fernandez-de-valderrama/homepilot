"""The guardrail's view of the current turn: the user message, the report in the session and the replies."""

import random
from typing import Any

from google.adk.agents.callback_context import CallbackContext

from smart_home_agent.guardrail.callbacks._content import content_text
from smart_home_agent.guardrail.replies import ResponseType, pick_response
from smart_home_agent.guardrail.report import GuardrailReport
from smart_home_agent.session import SessionState, StateKey, StateStore, TurnLanguageDetector


class GuardrailTurn:
    def __init__(self, context: CallbackContext) -> None:
        self._context = context

    @property
    def user_text(self) -> str:
        return content_text(self._context.user_content)

    @property
    def session(self) -> SessionState:
        return StateStore.read(self._context.state)

    def load_report(self) -> GuardrailReport:
        return GuardrailReport.model_validate(self._context.state.get(StateKey.GUARDRAIL) or {})

    def save_report(self, report: GuardrailReport) -> None:
        self._context.state[StateKey.GUARDRAIL] = report.model_dump(mode="json")

    def deterministic_reply(self, kind: ResponseType, rng: random.Random | None) -> str:
        """A reply of `kind` in the turn's language, never the same variant as the previous deterministic reply."""
        state = self._context.state
        reply = pick_response(kind, self._language(), state.get(StateKey.GUARDRAIL_LAST_REPLY), rng)
        state[StateKey.GUARDRAIL_LAST_REPLY] = reply
        return reply

    def tool_responses(self) -> list[dict[str, Any]]:
        """Function responses recorded in the session during the current invocation (this turn)."""
        return [
            dict(response.response or {})
            for event in self._context.session.events
            if event.invocation_id == self._context.invocation_id
            for response in event.get_function_responses()
        ]

    def _language(self) -> str | None:
        state = self._context.state
        return (
            state.get(StateKey.TURN_LANGUAGE)
            or StateStore.read(state).language
            or TurnLanguageDetector.detect(self.user_text)
        )
