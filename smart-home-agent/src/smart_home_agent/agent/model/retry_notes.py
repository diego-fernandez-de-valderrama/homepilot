"""Notes appended to a retried request (never to the session), since an identical retry gets the same answer."""

import copy

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
    request = copy_request(llm_request)
    request.contents.append(types.Content(role="user", parts=[types.Part(text=note)]))
    return request


def copy_request(llm_request: LlmRequest) -> LlmRequest:
    """A deep copy of the request that shares its tools: they wrap methods of tool objects holding the services
    (clients, engines, modules), which cannot be deep-copied, and a model call never changes them."""
    tools = llm_request.tools_dict
    return copy.deepcopy(llm_request, memo={id(tools): tools})
