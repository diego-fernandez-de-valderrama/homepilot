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

Without thinking the model also sometimes ends a turn by announcing work instead of doing it ("Please give me
a moment to search ..."), with no tool call, so the customer has to push it on. Such a stalled answer
(`announces_action`) is retried once, without delay, with a note asking it to do the work now; a second stalled
answer is passed on. A reply that ends with a question is never stalled (offering a search is legitimate).
"""

from collections.abc import AsyncGenerator, AsyncIterator

from google.adk.models import Gemini, LlmRequest, LlmResponse
from pydantic import Field

from smart_home_agent.agent.model.retry_policy import RetryPolicy
from smart_home_agent.agent.model.retrying import retry_empty_responses


class ResilientGemini(Gemini):
    """ADK's Gemini model plus silent retries of empty and stalled answers (see the module docstring)."""

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
        policy = RetryPolicy(self.empty_retries, self.retry_initial_delay, self.retry_max_delay)
        responses = retry_empty_responses(self._generate_once, llm_request, policy)
        async for response in responses:
            yield response

    def _generate_once(self, llm_request: LlmRequest) -> AsyncIterator[LlmResponse]:
        """One plain (non-streaming) Gemini call."""
        return super().generate_content_async(llm_request, stream=False)
