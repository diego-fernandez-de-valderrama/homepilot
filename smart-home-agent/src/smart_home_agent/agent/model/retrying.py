"""The retry loop around one non-streaming model call (see `resilient_gemini` for why it exists)."""

import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable

from google.adk.models import LlmRequest, LlmResponse
from tenacity import AsyncRetrying, RetryCallState, retry_if_result, stop_after_attempt

from smart_home_agent.agent.model.response_checks import is_empty, is_stalled
from smart_home_agent.agent.model.retry_notes import RETRY_NOTE, STALL_NOTE, copy_request, with_retry_note
from smart_home_agent.agent.model.retry_policy import RetryPolicy

logger = logging.getLogger(__name__)

Generate = Callable[[LlmRequest], AsyncIterator[LlmResponse]]
Sleep = Callable[[float], Awaitable[None]]


async def retry_empty_responses(
    generate: Generate, llm_request: LlmRequest, policy: RetryPolicy, sleep: Sleep = asyncio.sleep
) -> AsyncGenerator[LlmResponse, None]:
    """Runs a non-streaming call and repeats it while the answer is empty (with backoff), and once when it is
    stalled (`is_stalled`). Both share the empty-answer budget. After the last attempt the answer is passed on,
    so ADK still reports an empty one as an error event."""
    pristine = copy_request(llm_request)  # the model call adds to the request; each retry starts clean
    responses, spent = await _until_not_empty(generate, llm_request, pristine, policy.retries, policy, sleep)
    if responses and is_stalled(responses[-1]):
        logger.warning("model announced an action without doing it (after %s); retrying once", _last_turn(pristine))
        stalled_request = with_retry_note(pristine, STALL_NOTE)
        responses, more = await _until_not_empty(
            generate, stalled_request, pristine, policy.retries - spent, policy, sleep
        )
        spent += more
    if responses and is_empty(responses[-1]):
        logger.warning("model returned no content %d times in a row; giving up", spent + 1)
    elif spent:
        logger.info("model answered after %d silent retr%s", spent, "y" if spent == 1 else "ies")
    for response in responses:
        yield response


async def _until_not_empty(
    generate: Generate, first: LlmRequest, pristine: LlmRequest, retries: int, policy: RetryPolicy, sleep: Sleep
) -> tuple[list[LlmResponse], int]:
    """Calls with `first`, then with the retry note while the answer is empty, at most `retries` more times.
    Returns the last answer and the number of retries spent."""
    calls = 0

    async def attempt() -> list[LlmResponse]:
        nonlocal calls
        request = first if calls == 0 else with_retry_note(pristine, RETRY_NOTE)
        calls += 1
        return [response async for response in generate(request)]

    def log_retry(state: RetryCallState) -> None:
        last = state.outcome.result()[-1] if state.outcome else None
        logger.warning(
            "model returned no content (finish_reason=%s, after %s); retry %d of %d in %.1fs",
            last.finish_reason if last else None,
            _last_turn(pristine),
            state.attempt_number,
            retries,
            state.next_action.sleep if state.next_action else 0.0,
        )

    retrying = AsyncRetrying(
        retry=retry_if_result(lambda responses: bool(responses) and is_empty(responses[-1])),
        stop=stop_after_attempt(retries + 1),
        wait=policy.wait(),
        sleep=sleep,
        before_sleep=log_retry,
        retry_error_callback=lambda state: state.outcome.result() if state.outcome else [],
    )
    responses = await retrying(attempt)
    return responses, calls - 1


def _last_turn(llm_request: LlmRequest) -> str:
    """What the model was answering, for the log: the user's text or which tool results."""
    last = llm_request.contents[-1] if llm_request.contents else None
    if last is None or not last.parts:
        return "no content"
    tools = [part.function_response.name for part in last.parts if part.function_response]
    return f"tool results: {', '.join(n or '?' for n in tools)}" if tools else f"a {last.role} message"
