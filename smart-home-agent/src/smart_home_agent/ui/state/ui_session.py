import uuid

import streamlit as st

from smart_home_agent.agent import DEFAULT_USER
from smart_home_agent.session import SessionState, TurnLanguageDetector

# Session keys that survive "New conversation" and a customer switch (the customer, the picker widgets and the
# developer toggle).
_CUSTOMER_KEYS = frozenset(
    {"customer_id", "known_customers", "hp-customer-pick", "hp-customer-new", "hp-customer-options", "hp-debug"}
)


class UiSession:
    """The browser session in `st.session_state`: the customer, the conversation and its messages.

    A message is a dict with a `role`: "user" (`content`), "decision" (`confirmed`, `cancelled`) or "assistant"
    (`content`, `reply`, and `failed` + `language` when the turn produced nothing to show).
    """

    @staticmethod
    def init() -> None:
        state = st.session_state
        if "customer_id" not in state:
            state.customer_id = DEFAULT_USER
        if "known_customers" not in state:
            state.known_customers = []  # created in this browser session, maybe nothing stored yet
        if "session_id" not in state:
            state.session_id = str(uuid.uuid4())
            state.messages = []
            state.decisions = {}  # confirmation request id -> the customer's choice
            state.submitted = set()  # request ids already answered in a confirmation turn
            state.expired = set()  # request ids left open when the customer typed a new message
            state.cart_open = False  # the customer panel (cart and setup) on the right

    @staticmethod
    def customer_id() -> str:
        return st.session_state.customer_id

    @staticmethod
    def known_customers() -> list[str]:
        return st.session_state.known_customers

    @staticmethod
    def session_id() -> str:
        return st.session_state.session_id

    @staticmethod
    def messages() -> list[dict]:
        return st.session_state.messages

    @staticmethod
    def latest_state() -> SessionState | None:
        """The agent's session state after the latest answer (None before the first one)."""
        replies = [m["reply"] for m in UiSession.messages() if m.get("reply") is not None]
        return replies[-1].state if replies else None

    @staticmethod
    def reply_language(prompt: str | None) -> str | None:
        """Language for interface messages of this turn: the prompt's, else the conversation's."""
        detected = TurnLanguageDetector.detect(prompt) if prompt else None
        state = UiSession.latest_state()
        return detected or (state.language if state else None)

    @staticmethod
    def cart_open() -> bool:
        return st.session_state.cart_open

    @staticmethod
    def toggle_cart() -> None:
        st.session_state.cart_open = not st.session_state.cart_open

    @staticmethod
    def open_cart() -> None:
        st.session_state.cart_open = True

    @staticmethod
    def queue_prompt(prompt: str) -> None:
        """A prompt for the next script run (a welcome tile), handled there like a typed message."""
        st.session_state.pending_prompt = prompt

    @staticmethod
    def take_queued_prompt() -> str | None:
        return st.session_state.pop("pending_prompt", None)

    @staticmethod
    def reset_conversation() -> None:
        """Starts a new conversation for the same customer: their stored memory carries over."""
        for key in list(st.session_state.keys()):
            if key not in _CUSTOMER_KEYS:
                del st.session_state[key]
        UiSession.init()

    @staticmethod
    def switch_customer(customer: str) -> None:
        """Another customer: a new conversation, with that customer's memory. Both stay in the picker for this
        browser session, even while nothing is stored for them yet."""
        if customer != st.session_state.customer_id:
            known = [st.session_state.customer_id, *st.session_state.known_customers, customer]
            st.session_state.known_customers = list(dict.fromkeys(known))
            st.session_state.customer_id = customer
            UiSession.reset_conversation()
