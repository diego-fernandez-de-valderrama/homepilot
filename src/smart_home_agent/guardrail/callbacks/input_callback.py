"""`before_agent_callback`: classifies the user message once per turn, before the first model call.

Returning a Content makes ADK end the invocation with that content as the agent's reply, so the model is never
called for a blocked message.
"""

import asyncio
import logging
import random

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from smart_home_agent.guardrail.callbacks._content import model_reply
from smart_home_agent.guardrail.callbacks._guardrail_turn import GuardrailTurn
from smart_home_agent.guardrail.input import SemanticGuardrail
from smart_home_agent.guardrail.replies import ResponseType
from smart_home_agent.guardrail.report import GuardrailReport

logger = logging.getLogger(__name__)


class InputGuardrailCallback:
    def __init__(self, guardrail: SemanticGuardrail, rng: random.Random | None = None) -> None:
        self._guardrail = guardrail
        self._rng = rng

    async def __call__(self, callback_context: CallbackContext) -> types.Content | None:
        turn = GuardrailTurn(callback_context)
        text = turn.user_text
        if not text:
            return None
        report = GuardrailReport()
        try:
            # The embedding client is synchronous; keep the shared agent event loop free.
            report.input = await asyncio.to_thread(self._guardrail.classify, text)
        except Exception as exc:
            # Fail open: the prompt-level guardrails of the agent still apply.
            logger.warning("guardrail: input classification failed, message allowed: %s", exc)
            report.input_error = f"{type(exc).__name__}: {exc}"
        decision = report.input
        if decision is not None:
            logger.info(
                "guardrail: %s (top=%s score=%.3f margin=%.3f)",
                decision.category,
                decision.top_category,
                decision.score,
                decision.margin,
            )
        if decision is None or not decision.blocked:
            turn.save_report(report)
            return None
        report.response_type = ResponseType(decision.category.value)
        turn.save_report(report)
        return model_reply(turn.deterministic_reply(report.response_type, self._rng))
