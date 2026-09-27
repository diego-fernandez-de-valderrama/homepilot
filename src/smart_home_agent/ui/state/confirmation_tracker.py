import streamlit as st

from smart_home_agent.models import CartConfirmation
from smart_home_agent.ui.components import ConfirmationState
from smart_home_agent.ui.state.ui_session import UiSession


class ConfirmationTracker:
    """The cart changes the advisor proposed and what the customer did with them.

    Only the latest answer can have open changes. Each is decided on its card (`decide`); once all are decided,
    `ready_decisions` hands them to the confirmation turn (`mark_submitted`). A new typed message expires the
    open ones instead (`expire_open`): they are never sent later. A failed confirmation turn reopens the changes
    that did not run (`reopen`).
    """

    @staticmethod
    def open() -> list[CartConfirmation]:
        """Changes of the latest answer that were neither answered nor expired."""
        messages = UiSession.messages()
        last = messages[-1] if messages else None
        reply = last.get("reply") if last and last["role"] == "assistant" else None
        if reply is None:
            return []
        done = st.session_state.submitted | st.session_state.expired
        return [c for c in reply.pending_confirmations if c.request_id not in done]

    @staticmethod
    def ready_decisions() -> dict[str, bool] | None:
        """The customer's choices once every open change of the latest answer has one."""
        pending = ConfirmationTracker.open()
        if not pending or any(c.request_id not in st.session_state.decisions for c in pending):
            return None
        return {c.request_id: st.session_state.decisions[c.request_id] for c in pending}

    @staticmethod
    def decide(request_id: str, confirmed: bool) -> None:
        st.session_state.decisions[request_id] = confirmed

    @staticmethod
    def state_of(request_id: str) -> ConfirmationState:
        if request_id in st.session_state.expired:
            return "expired"
        if request_id in st.session_state.decisions:
            return "confirmed" if st.session_state.decisions[request_id] else "cancelled"
        return None

    @staticmethod
    def expire_open() -> None:
        st.session_state.expired |= {c.request_id for c in ConfirmationTracker.open()}

    @staticmethod
    def mark_submitted(request_ids: set[str]) -> None:
        st.session_state.submitted |= request_ids

    @staticmethod
    def reopen(request_ids: set[str]) -> None:
        """Their cards take a decision again (the confirmation turn failed before they ran)."""
        st.session_state.submitted -= request_ids
        for request_id in request_ids:
            st.session_state.decisions.pop(request_id, None)
