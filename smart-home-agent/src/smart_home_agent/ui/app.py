import streamlit as st

from smart_home_agent.models import CartView
from smart_home_agent.ui.backend import AgentBackend
from smart_home_agent.ui.page_assets import PageAssets
from smart_home_agent.ui.state import ConfirmationTracker, UiSession
from smart_home_agent.ui.turns import ConfirmationTurn, MessageTurn
from smart_home_agent.ui.views import CartPanel, Masthead, MessageView, Sidebar, Welcome


class HomePilotApp:
    """One Streamlit script run (see the `ui` package docstring for the flow)."""

    def run(self) -> None:
        st.set_page_config(page_title="HomePilot", page_icon=PageAssets.ADVISOR_AVATAR, layout="centered")
        PageAssets.inject()
        UiSession.init()

        prompt = self._read_prompt()
        decisions = None if prompt else ConfirmationTracker.ready_decisions()
        busy = bool(prompt or decisions)

        debug = Sidebar.render(busy)
        cart = self._current_cart()
        Masthead.render(cart, busy)
        CartPanel.render(cart, busy)
        self._render_history(debug)

        if decisions:
            ConfirmationTurn.run(decisions, debug)
        elif prompt:
            MessageTurn.run(prompt, debug)
        elif not UiSession.messages() and (tile := Welcome.render()):
            UiSession.queue_prompt(tile)  # runs in the next script run, so `busy` covers it like a typed message
            st.rerun()

    @staticmethod
    def _read_prompt() -> str | None:
        """The typed message, else a welcome tile's. An open cart change blocks the input: the customer answers it
        on its card first."""
        awaiting_decision = bool(ConfirmationTracker.open())
        placeholder = (
            "Confirm or cancel the cart change above to continue"
            if awaiting_decision
            else "Ask about smart home products..."
        )
        typed = st.chat_input(placeholder, submit_mode="disable", disabled=awaiting_decision)
        prompt = typed or UiSession.take_queued_prompt()
        if prompt:  # guard only (the input is disabled then): the open changes stay unconfirmed, never sent later
            ConfirmationTracker.expire_open()
        return prompt

    @staticmethod
    def _current_cart() -> CartView:
        """Before the first message the agent service is not built yet and the new session's cart is empty
        anyway."""
        if not UiSession.messages():
            return CartView()
        return AgentBackend.cart(UiSession.session_id(), UiSession.customer_id())

    @staticmethod
    def _render_history(debug: bool) -> None:
        messages = UiSession.messages()
        for index, message in enumerate(messages):
            MessageView.render(message, debug, is_last=index == len(messages) - 1)
