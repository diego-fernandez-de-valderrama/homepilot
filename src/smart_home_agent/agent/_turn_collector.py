import logging
from collections.abc import Callable
from typing import Any

from google.adk.events import Event
from google.adk.flows.llm_flows.functions import REQUEST_CONFIRMATION_FUNCTION_CALL_NAME

from smart_home_agent.agent.reply import TurnTrace
from smart_home_agent.tools import CONFIRMED_TOOLS

logger = logging.getLogger(__name__)

# (confirmation request id, cart tool name, cart tool args)
ConfirmationRequest = tuple[str, str, dict[str, Any]]


class TurnCollector:
    """Reads the ADK events of one turn: the tool trace, the answer text, cart confirmation requests and errors."""

    def __init__(self, on_tool_call: Callable[[str], None] | None = None) -> None:
        self.trace = TurnTrace()
        self.confirmation_requests: list[ConfirmationRequest] = []
        self._on_tool_call = on_tool_call
        self._answer: list[str] = []
        self._errors: list[str] = []

    @property
    def answer(self) -> str:
        return "".join(self._answer).strip()

    @property
    def error(self) -> str | None:
        return "; ".join(self._errors) or None

    def add(self, event: Event) -> None:
        for call in event.get_function_calls():
            if call.name == REQUEST_CONFIRMATION_FUNCTION_CALL_NAME:
                original = (call.args or {}).get("originalFunctionCall") or {}
                if call.id and original.get("name") in CONFIRMED_TOOLS:
                    self.confirmation_requests.append((call.id, original["name"], dict(original.get("args") or {})))
                continue
            self.trace.add_call(call.id, call.name or "", dict(call.args or {}))
            if self._on_tool_call is not None:
                self._on_tool_call(call.name or "")
        for response in event.get_function_responses():
            self.trace.add_response(response.id, response.name or "", response.response)
        if event.is_final_response() and event.content and event.content.parts:
            self._answer.extend(part.text for part in event.content.parts if part.text and not part.thought)
        if event.error_message:
            logger.warning("agent error event: %s", event.error_message)
            self._errors.append(event.error_message)
