from google.adk.flows.llm_flows.functions import REQUEST_CONFIRMATION_FUNCTION_CALL_NAME
from google.genai import types

from smart_home_agent.agent._session_store import SessionStore


class ConfirmationLedger:
    """ADK's confirmation requests for cart changes: which were already applied, and the message answering them."""

    def __init__(self, sessions: SessionStore) -> None:
        self._sessions = sessions

    async def applied(self, session_id: str, request_ids: list[str], user_id: str) -> set[str]:
        """Confirmation requests that were answered and whose cart tool then ran (or was cancelled) in this
        session: the tool's function response follows the customer's answer. Such a request must not be
        answered again."""
        session = await self._sessions.get(session_id, user_id)
        if session is None:
            return set()
        wanted = set(request_ids)
        originals: dict[str, str] = {}  # confirmation request id -> id of the paused cart tool call
        answered_at: dict[str, int] = {}  # confirmation request id -> index of the customer's answer
        for index, event in enumerate(session.events):
            for call in event.get_function_calls():
                if call.name == REQUEST_CONFIRMATION_FUNCTION_CALL_NAME and call.id in wanted:
                    original = (call.args or {}).get("originalFunctionCall") or {}
                    if original.get("id"):
                        originals[call.id] = original["id"]
            for response in event.get_function_responses():
                if response.name == REQUEST_CONFIRMATION_FUNCTION_CALL_NAME and response.id in wanted:
                    answered_at.setdefault(response.id, index)
        applied: set[str] = set()
        for request_id, start in answered_at.items():
            original_id = originals.get(request_id)
            later = session.events[start + 1 :]
            if original_id and any(r.id == original_id for e in later for r in e.get_function_responses()):
                applied.add(request_id)
        return applied

    @staticmethod
    def answer(decisions: dict[str, bool]) -> types.Content:
        """The customer's decisions (request id -> confirmed) as the user message ADK expects."""
        parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    id=request_id, name=REQUEST_CONFIRMATION_FUNCTION_CALL_NAME, response={"confirmed": confirmed}
                )
            )
            for request_id, confirmed in decisions.items()
        ]
        return types.Content(role="user", parts=parts)
