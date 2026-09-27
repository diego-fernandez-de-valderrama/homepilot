"""`after_model_callback`: removes answer tags that would never be rendered (`rich.strip_invalid_tags`), then checks
the final text answer and replaces it with a fallback when a critical check fails.

The returned response is what ADK records, so the next model call never sees a removed tag or a rejected answer.
"""

import asyncio
import logging
import random

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse

from smart_home_agent.guardrail.callbacks._content import content_text, model_reply, with_text
from smart_home_agent.guardrail.callbacks._fallback import fallback_type
from smart_home_agent.guardrail.callbacks._guardrail_turn import GuardrailTurn
from smart_home_agent.guardrail.output import OutputValidator, Violation
from smart_home_agent.models import rich

logger = logging.getLogger(__name__)


class OutputGuardrailCallback:
    """`validator`: None only removes invalid tags (AGENT_GUARDRAIL_OUTPUT_CHECK=false)."""

    def __init__(self, validator: OutputValidator | None, rng: random.Random | None = None) -> None:
        self._validator = validator
        self._rng = rng

    async def __call__(self, callback_context: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None:
        content = llm_response.content
        if llm_response.partial or not content or not content.parts:
            return None
        if any(part.function_call for part in content.parts):
            return None  # intermediate step: only the final text answer is validated
        text = content_text(content)
        if not text:
            return None
        turn = GuardrailTurn(callback_context)
        session = turn.session
        upsell = session.last_upsell
        cleaned = rich.strip_invalid_tags(text, (upsell.base_product_id, upsell.product_id) if upsell else None)
        if cleaned != text:
            logger.info("answer: invalid tags removed")
        violations: list[Violation] = []
        if cleaned and self._validator is not None:
            known = [
                *session.selected_products,
                *session.comparison_products,
                *session.candidate_products,
                *(item.product_id for item in session.cart),
            ]
            violations = await asyncio.to_thread(self._validator.validate, cleaned, turn.tool_responses(), known)
        if cleaned and not violations:
            return with_text(llm_response, cleaned) if cleaned != text else None
        report = turn.load_report()
        if violations:
            logger.warning("guardrail: answer replaced, %s", "; ".join(f"{v.kind}: {v.detail}" for v in violations))
            report.output_violations = violations
        report.response_type = fallback_type(violations)  # nothing left after removing the tags: generic fallback
        turn.save_report(report)
        return LlmResponse(content=model_reply(turn.deterministic_reply(report.response_type, self._rng)))
