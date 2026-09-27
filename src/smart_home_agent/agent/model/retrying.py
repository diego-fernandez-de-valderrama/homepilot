"""The retry loop around one non-streaming model call (see `resilient_gemini` for why it exists)."""

import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable

from google.adk.models import LlmRequest, LlmResponse

from smart_home_agent.agent.model.response_checks import is_empty, is_stalled
from smart_home_agent.agent.model.retry_notes import RETRY_NOTE, STALL_NOTE, copy_request, with_retry_note
from smart_home_agent.agent.model.retry_policy import RetryPolicy

logger = logging.getLogger(__name__)

Generate = Callable[[LlmRequest], AsyncIterator[LlmResponse]]


async def retry_empty_responses(
    generate: Generate,
    llm_request: LlmRequest,
    policy: RetryPolicy,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncGenerator[LlmResponse, None]:
    """Runs a non-streaming call and repeats it while the answer is empty (with backoff), and once when it is
    stalled (`is_stalled`). After the last attempt the answer is passed on, so ADK still reports an empty one
    as an error event."""
    pristine = copy_request(llm_request)  # the model call adds to the request; each retry starts clean
    note: str | None = None
    attempt = 0  # empty-answer retries spent
    stall_retried = False
    while True:
        request = llm_request if note is None else with_retry_note(pristine, note)
        responses = [response async for response in generate(request)]
        last = responses[-1] if responses else None
        if last is not None and is_empty(last) and attempt < policy.retries:
            delay = policy.delay(attempt)
            logger.warning(
                "model returned no content (finish_reason=%s, after %s); retry %d of %d in %.1fs",
                last.finish_reason,
                _last_turn(llm_request),
                attempt + 1,
                policy.retries,
                delay,
            )
            attempt += 1
            note = RETRY_NOTE
            await sleep(delay)
            continue
        if last is not None and not stall_retried and is_stalled(last):
            logger.warning(
                "model announced an action without doing it (after %s); retrying once", _last_turn(llm_request)
            )
            stall_retried = True
            note = STALL_NOTE
            continue
        if last is not None and is_empty(last):
            logger.warning("model returned no content %d times in a row; giving up", attempt + 1)
        elif attempt:
            logger.info("model answered after %d silent retr%s", attempt, "y" if attempt == 1 else "ies")
        for response in responses:
            yield response
        return


def _last_turn(llm_request: LlmRequest) -> str:
    """What the model was answering, for the log: the user's text or which tool results."""
    last = llm_request.contents[-1] if llm_request.contents else None
    if last is None or not last.parts:
        return "no content"
    tools = [part.function_response.name for part in last.parts if part.function_response]
    return f"tool results: {', '.join(n or '?' for n in tools)}" if tools else f"a {last.role} message"
