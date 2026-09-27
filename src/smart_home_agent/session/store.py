"""Reading and writing the `SessionState` in the ADK session state."""

from collections.abc import Mapping
from typing import Any

from google.adk.sessions.state import State

from smart_home_agent.session.keys import STATE_KEY
from smart_home_agent.session.session_state import SessionState
from smart_home_agent.session.state_holder import StateHolder


def read_state(state: Mapping[str, Any] | State) -> SessionState:
    return SessionState.model_validate(state.get(STATE_KEY) or {})


def load_state(context: StateHolder) -> SessionState:
    return read_state(context.state)


def save_state(context: StateHolder, session_state: SessionState) -> None:
    # Assign the whole value: ADK records assignments (not in-place mutations) as state deltas.
    context.state[STATE_KEY] = session_state.model_dump(mode="json")
