import streamlit as st

from smart_home_agent.ui.backend import AgentBackend
from smart_home_agent.ui.state import ConfirmationTracker, UiSession
from smart_home_agent.ui.turns.answer_turn import AnswerTurn
from smart_home_agent.ui.views import MessageView


class ConfirmationTurn:
    """Sends the customer's decisions on the open cart changes; the cart tools run only now."""

    @staticmethod
    def run(decisions: dict[str, bool], debug: bool) -> None:
        """Records the decision in the history and runs the confirmation turn. On success the page reruns
        (opening the cart panel after a confirmed add); on failure only the changes that did not run reopen."""
        session_id, customer_id = UiSession.session_id(), UiSession.customer_id()
        adds = {c.request_id for c in ConfirmationTracker.open() if c.action == "add"}
        ConfirmationTracker.mark_submitted(set(decisions))
        confirmed = sum(decisions.values())
        decision = {"role": "decision", "confirmed": confirmed, "cancelled": len(decisions) - confirmed}
        messages = UiSession.messages()
        messages.append(decision)
        MessageView.render(decision, debug)
        start = AgentBackend.confirmation_turn(session_id, decisions, customer_id)
        if not AnswerTurn.run(start, debug, UiSession.reply_language(None)):
            # The turn may have failed after a cart change was applied: only the others open again for a retry.
            retry = set(decisions) - AgentBackend.applied_confirmations(session_id, list(decisions), customer_id)
            if len(retry) == len(decisions):
                messages.pop()  # nothing happened: the cards open again, so the customer can retry
            ConfirmationTracker.reopen(retry)
            return
        if any(decisions[r] for r in adds):  # show the customer what they just added
            UiSession.open_cart()
        st.rerun()
