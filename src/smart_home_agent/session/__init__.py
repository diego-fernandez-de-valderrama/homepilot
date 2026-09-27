"""Conversation state, kept in the ADK session (in memory, per conversation; nothing is persisted). Import everything
from here:

    from smart_home_agent.session import SessionState, StateKey, StateStore, ...

Flow:

1. `StateKey` names every ADK session state entry HomePilot uses.
2. `state/`: `SessionState` (everything kept about one conversation) is stored whole under `StateKey.HOMEPILOT`.
   `StateStore.load` / `StateStore.save` read and write it through a `StateHolder` (ADK's ToolContext or
   CallbackContext); `StateStore.read` takes a raw state mapping. Always save a whole new value: ADK records
   assignments, not in-place mutations.
3. `language/`: `TurnLanguageDetector.detect` gives the per-turn English/German hint the agent service writes under
   `StateKey.TURN_LANGUAGE`.

Shared by the agent, the tools, the guardrail and the interface; it imports nothing from them.
"""

from smart_home_agent.session.language import TurnLanguageDetector
from smart_home_agent.session.state import CentralUnitsAsked, SessionState, StateHolder, StateStore
from smart_home_agent.session.state_key import StateKey

__all__ = [
    "CentralUnitsAsked",
    "SessionState",
    "StateHolder",
    "StateKey",
    "StateStore",
    "TurnLanguageDetector",
]
