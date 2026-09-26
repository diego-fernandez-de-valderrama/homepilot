"""Gemini chat model with silent retries.

Gemini 2.5 Flash sometimes ends a call at once with finish_reason=STOP, no parts and zero output tokens
(ADK reports it as MODEL_RETURNED_NO_CONTENT). The main cause was its dynamic thinking: with an explicit
budget (AGENT_THINKING_BUDGET, default 0) it no longer happened in live tests, so this retry is the safety net.
For a given prompt the empty answer is close to deterministic: repeating the identical request (or raising the
temperature) gives the same empty answer, measured 0 of 3 rescued. A retry whose request ends with a short
note asking for the answer was rescued 3 of 3, so every retry adds that note to its own copy of the request;
it is never stored in the session. Only the model call is repeated, never the
tools that already ran, so nothing (a cart change, a stored fact) happens twice. Transient HTTP errors
(408, 429, 5xx) are retried by the genai client with the same exponential backoff.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable

from google.adk.models import Gemini, LlmRequest, LlmResponse
from google.genai import types
from pydantic import Field

logger = logging.getLogger(__name__)

Generate = Callable[[LlmRequest], AsyncIterator[LlmResponse]]


# Appended to the retry request only (never to the session); the model must not mention it.
RETRY_NOTE = (
    "(System note: your previous reply was empty. Answer the customer's last message now, calling tools if "
    "needed. Do not mention this note.)"
)


def is_empty(response: LlmResponse) -> bool:
    """A finished answer without anything usable: no parts, or only thoughts (never shown to the customer)."""
    if response.partial or response.error_code is not None:
        return False
    if response.finish_reason not in (None, types.FinishReason.STOP):
        return False
    parts = response.content.parts if response.content else None
    return not any((part.text and not part.thought) or part.function_call for part in parts or [])


def backoff(attempt: int, initial_delay: float, max_delay: float) -> float:
    """Delay before retry number `attempt` (0-based): initial, 2x, 4x ..., capped."""
    return min(initial_delay * 2**attempt, max_delay)


async def retry_empty_responses(
    generate: Generate,
    llm_request: LlmRequest,
    retries: int,
    initial_delay: float,
    max_delay: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncGenerator[LlmResponse, None]:
    """Runs a non-streaming call and repeats it while the answer is empty. After the last attempt the empty
    answer is passed on, so ADK still reports it as an error event."""
    pristine = llm_request.model_copy(deep=True)  # the model call adds to the request; each retry starts clean
    for attempt in range(retries + 1):
        request = llm_request if attempt == 0 else with_retry_note(pristine)
        responses = [response async for response in generate(request)]
        if not responses or not is_empty(responses[-1]) or attempt == retries:
            if attempt and responses and not is_empty(responses[-1]):
                logger.info("model answered after %d silent retr%s", attempt, "y" if attempt == 1 else "ies")
            elif attempt == retries and responses and is_empty(responses[-1]):
                logger.warning("model returned no content %d times in a row; giving up", attempt + 1)
            for response in responses:
                yield response
            return
        delay = backoff(attempt, initial_delay, max_delay)
        logger.warning(
            "model returned no content (finish_reason=%s, after %s); retry %d of %d in %.1fs",
            responses[-1].finish_reason,
            _last_turn(llm_request),
            attempt + 1,
            retries,
            delay,
        )
        await sleep(delay)


def with_retry_note(llm_request: LlmRequest) -> LlmRequest:
    """A copy of the request that ends with RETRY_NOTE (an identical retry would get the same empty answer)."""
    request = llm_request.model_copy(deep=True)
    request.contents.append(types.Content(role="user", parts=[types.Part(text=RETRY_NOTE)]))
    return request


def _last_turn(llm_request: LlmRequest) -> str:
    """What the model was answering, for the log: the user's text or which tool results."""
    last = llm_request.contents[-1] if llm_request.contents else None
    if last is None or not last.parts:
        return "no content"
    tools = [part.function_response.name for part in last.parts if part.function_response]
    return f"tool results: {', '.join(n or '?' for n in tools)}" if tools else f"a {last.role} message"


class ResilientGemini(Gemini):
    """ADK's Gemini model plus silent retries of empty answers (see the module docstring)."""

    empty_retries: int = Field(default=3, ge=0)
    retry_initial_delay: float = Field(default=1.0, ge=0.0)
    retry_max_delay: float = Field(default=8.0, ge=0.0)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if stream:  # a streamed answer is judged by ADK on the aggregate; not used by this agent
            async for response in super().generate_content_async(llm_request, stream=True):
                yield response
            return
        responses = retry_empty_responses(
            self._generate_once,
            llm_request,
            self.empty_retries,
            self.retry_initial_delay,
            self.retry_max_delay,
        )
        async for response in responses:
            yield response

    def _generate_once(self, llm_request: LlmRequest) -> AsyncIterator[LlmResponse]:
        """One plain (non-streaming) Gemini call."""
        return super().generate_content_async(llm_request, stream=False)


def http_retry_options(retries: int, initial_delay: float, max_delay: float) -> types.HttpRetryOptions:
    """Same backoff for transient HTTP errors (the genai client's default status codes: 408, 429, 5xx)."""
    return types.HttpRetryOptions(attempts=retries + 1, initial_delay=initial_delay, max_delay=max_delay, exp_base=2.0)
