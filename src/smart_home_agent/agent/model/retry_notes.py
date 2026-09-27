"""Notes appended to a retried request (never to the session), since an identical retry gets the same answer."""

from google.adk.models import LlmRequest
from google.genai import types

# Appended to the retry request only (never to the session); the model must not mention it.
RETRY_NOTE = (
    "(System note: your previous reply was empty. Answer the customer's last message now, calling tools if "
    "needed. Do not mention this note.)"
)

STALL_NOTE = (
    "(System note: your previous reply announced an action but did not do it. Do it now: call the tools "
    "needed and answer with the result. Do not announce it, and do not mention this note.)"
)


def with_retry_note(llm_request: LlmRequest, note: str = RETRY_NOTE) -> LlmRequest:
    """A copy of the request that ends with `note` (an identical retry would get the same answer)."""
    request = llm_request.model_copy(deep=True)
    request.contents.append(types.Content(role="user", parts=[types.Part(text=note)]))
    return request
