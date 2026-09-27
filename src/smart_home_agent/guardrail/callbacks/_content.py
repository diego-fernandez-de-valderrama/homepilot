"""Reads and replaces the text of ADK model content."""

from google.adk.models import LlmResponse
from google.genai import types


def content_text(content: types.Content | None) -> str:
    """The visible text of `content` (thought parts excluded)."""
    if not content or not content.parts:
        return ""
    return "".join(part.text for part in content.parts if part.text and not part.thought).strip()


def with_text(response: LlmResponse, text: str) -> LlmResponse:
    """`response` with its text replaced by `text` (thought parts kept)."""
    thoughts = [part for part in (response.content.parts or []) if part.thought] if response.content else []
    return response.model_copy(
        update={"content": types.Content(role="model", parts=[*thoughts, types.Part(text=text)])}
    )


def model_reply(text: str) -> types.Content:
    """A deterministic reply authored as the model's own turn, so ADK keeps it in the history as such."""
    return types.Content(role="model", parts=[types.Part(text=text)])
