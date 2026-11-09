"""Streamlit renderers, one class per screen region (widgets plus `st.html` from `ui.components`).

- rail and page frame: `Sidebar` (with `CustomerPicker` and `CustomerMemoryDialog`), `Masthead`, `CartPanel`
  (cart lines, quantity stepper, setup), `Welcome` (intro and example tiles);
- the conversation: `MessageView` draws one history message; an answer is `AnswerView` (answer tags ->
  components), then `ConfirmationCards` (cart changes), `DebugPanel` (developer mode) or `FailureNotice`.
"""

from smart_home_agent.ui.views.answer_view import AnswerView
from smart_home_agent.ui.views.cart_panel import CartPanel
from smart_home_agent.ui.views.confirmation_cards import ConfirmationCards
from smart_home_agent.ui.views.customer_memory_dialog import CustomerMemoryDialog
from smart_home_agent.ui.views.customer_picker import CustomerPicker
from smart_home_agent.ui.views.debug_panel import DebugPanel
from smart_home_agent.ui.views.failure_notice import FailureNotice
from smart_home_agent.ui.views.masthead import Masthead
from smart_home_agent.ui.views.message_view import MessageView
from smart_home_agent.ui.views.sidebar import Sidebar
from smart_home_agent.ui.views.welcome import Welcome

__all__ = [
    "AnswerView",
    "CartPanel",
    "ConfirmationCards",
    "CustomerMemoryDialog",
    "CustomerPicker",
    "DebugPanel",
    "FailureNotice",
    "Masthead",
    "MessageView",
    "Sidebar",
    "Welcome",
]
