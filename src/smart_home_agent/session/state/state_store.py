from collections.abc import Mapping
from typing import Any

from google.adk.sessions.state import State

from smart_home_agent.session.state.session_state import SessionState
from smart_home_agent.session.state.state_holder import StateHolder
from smart_home_agent.session.state_key import StateKey


class StateStore:
    """Reads and writes the `SessionState` stored whole under `StateKey.HOMEPILOT`."""

    @staticmethod
    def read(state: Mapping[str, Any] | State) -> SessionState:
        """From a raw session state (a stored session, outside a tool or callback)."""
        return SessionState.model_validate(state.get(StateKey.HOMEPILOT) or {})

    @staticmethod
    def load(context: StateHolder) -> SessionState:
        """From a ToolContext / CallbackContext."""
        return StateStore.read(context.state)

    @staticmethod
    def save(context: StateHolder, session_state: SessionState) -> None:
        # Assign the whole value: ADK records assignments (not in-place mutations) as state deltas.
        context.state[StateKey.HOMEPILOT] = session_state.model_dump(mode="json")
