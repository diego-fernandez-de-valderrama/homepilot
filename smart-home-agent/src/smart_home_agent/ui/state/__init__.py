"""Typed access to `st.session_state`; nothing here draws.

- `UiSession`: the customer, the conversation id, the message history, the customer panel toggle and the prompt
  queued by a welcome tile; `reset_conversation` / `switch_customer` start a new conversation;
- `ConfirmationTracker`: the lifecycle of proposed cart changes (open -> decided -> submitted, or expired).
"""

from smart_home_agent.ui.state.confirmation_tracker import ConfirmationTracker
from smart_home_agent.ui.state.ui_session import UiSession

__all__ = ["ConfirmationTracker", "UiSession"]
