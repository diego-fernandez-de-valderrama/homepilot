"""ADK callbacks that put the guardrail around the existing agent (no second agent).

- `before_agent_callback` (input): runs once per turn, before the first model call. Returning a
  Content makes ADK end the invocation with that content as the agent's reply, so the model is never
  called for a blocked message.
- `after_model_callback` (output): removes answer tags that would never be rendered (`rich.strip_invalid_tags`),
  then checks the final text answer and replaces it with a fallback when a critical check fails. The
  returned response is what ADK records, so the next model call never sees a removed tag either.

Deterministic replies use role "model" and are authored by the agent itself, so ADK keeps them in
the history as the model's own previous turns (not as "[agent] said" context). The next model call
sees exactly what the user saw, and a rejected answer never enters the history.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types

from smart_home_agent.guardrail.classifier import SemanticGuardrail
from smart_home_agent.guardrail.output_check import OutputValidator, Violation
from smart_home_agent.guardrail.report import GuardrailReport
from smart_home_agent.guardrail.responses import ResponseType, pick_response
from smart_home_agent.models import rich
from smart_home_agent.session import (
    GUARDRAIL_KEY,
    GUARDRAIL_LAST_REPLY_KEY,
    TURN_LANGUAGE_KEY,
    detect_language,
    read_state,
)

logger = logging.getLogger(__name__)


def _text(content: types.Content | None) -> str:
    if not content or not content.parts:
        return ""
    return "".join(part.text for part in content.parts if part.text and not part.thought).strip()


def _language(context: CallbackContext, user_text: str) -> str | None:
    return context.state.get(TURN_LANGUAGE_KEY) or read_state(context.state).language or detect_language(user_text)


def _report(context: CallbackContext) -> GuardrailReport:
    return GuardrailReport.model_validate(context.state.get(GUARDRAIL_KEY) or {})


def _save(context: CallbackContext, report: GuardrailReport) -> None:
    context.state[GUARDRAIL_KEY] = report.model_dump(mode="json")


def _deterministic_reply(context: CallbackContext, kind: ResponseType, rng: random.Random | None) -> str:
    user_text = _text(context.user_content)
    reply = pick_response(kind, _language(context, user_text), context.state.get(GUARDRAIL_LAST_REPLY_KEY), rng)
    context.state[GUARDRAIL_LAST_REPLY_KEY] = reply
    return reply


def make_input_callback(
    guardrail: SemanticGuardrail, rng: random.Random | None = None
) -> Callable[[CallbackContext], Awaitable[types.Content | None]]:
    async def semantic_input_guardrail(callback_context: CallbackContext) -> types.Content | None:
        text = _text(callback_context.user_content)
        if not text:
            return None
        report = GuardrailReport()
        try:
            # The embedding client is synchronous; keep the shared agent event loop free.
            report.input = await asyncio.to_thread(guardrail.classify, text)
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
            _save(callback_context, report)
            return None
        report.response_type = ResponseType(decision.category.value)
        _save(callback_context, report)
        reply = _deterministic_reply(callback_context, report.response_type, rng)
        return types.Content(role="model", parts=[types.Part(text=reply)])

    return semantic_input_guardrail


def _tool_responses(context: CallbackContext) -> list[dict[str, Any]]:
    """Function responses recorded in the session during the current invocation (this turn)."""
    return [
        dict(response.response or {})
        for event in context.session.events
        if event.invocation_id == context.invocation_id
        for response in event.get_function_responses()
    ]


# Which deterministic reply replaces an answer, by the most severe violation it contains.
_FALLBACKS = (
    ("electrical", ResponseType.ELECTRICAL),
    ("prompt_leak", ResponseType.PROMPT_INJECTION),
    ("off_topic", ResponseType.OFF_TOPIC),
)


def _fallback_type(violations: list[Violation]) -> ResponseType:
    kinds = {v.kind for v in violations}
    return next((response for kind, response in _FALLBACKS if kind in kinds), ResponseType.OUTPUT_FALLBACK)


def _with_text(response: LlmResponse, text: str) -> LlmResponse:
    thoughts = [part for part in (response.content.parts or []) if part.thought] if response.content else []
    return response.model_copy(
        update={"content": types.Content(role="model", parts=[*thoughts, types.Part(text=text)])}
    )


def make_output_callback(
    validator: OutputValidator | None, rng: random.Random | None = None
) -> Callable[[CallbackContext, LlmResponse], Awaitable[LlmResponse | None]]:
    """`validator`: None only removes invalid tags (AGENT_GUARDRAIL_OUTPUT_CHECK=false)."""

    async def output_validation(callback_context: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None:
        content = llm_response.content
        if llm_response.partial or not content or not content.parts:
            return None
        if any(part.function_call for part in content.parts):
            return None  # intermediate step: only the final text answer is validated
        text = _text(content)
        if not text:
            return None
        session = read_state(callback_context.state)
        upsell = session.last_upsell
        cleaned = rich.strip_invalid_tags(text, (upsell.base_product_id, upsell.product_id) if upsell else None)
        if cleaned != text:
            logger.info("answer: invalid tags removed")
        report = _report(callback_context)
        violations: list[Violation] = []
        if cleaned and validator is not None:
            known = [
                *session.selected_products,
                *session.comparison_products,
                *session.candidate_products,
                *(item.product_id for item in session.cart),
            ]
            violations = await asyncio.to_thread(validator.validate, cleaned, _tool_responses(callback_context), known)
        if cleaned and not violations:
            return _with_text(llm_response, cleaned) if cleaned != text else None
        if violations:
            logger.warning("guardrail: answer replaced, %s", "; ".join(f"{v.kind}: {v.detail}" for v in violations))
            report.output_violations = violations
        report.response_type = _fallback_type(violations)  # nothing left after removing the tags: generic fallback
        _save(callback_context, report)
        reply = _deterministic_reply(callback_context, report.response_type, rng)
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=reply)]))

    return output_validation
