import streamlit as st

from smart_home_agent.ui.backend import AgentBackend
from smart_home_agent.ui.state import UiSession
from smart_home_agent.ui.turns.answer_turn import AnswerTurn
from smart_home_agent.ui.views import MessageView


class MessageTurn:
    """Sends a typed (or tile) message and answers it."""

    @staticmethod
    def run(prompt: str, debug: bool) -> None:
        user_message = {"role": "user", "content": prompt}
        messages = UiSession.messages()
        messages.append(user_message)
        MessageView.render(user_message, debug)
        start = AgentBackend.message_turn(UiSession.session_id(), prompt, UiSession.customer_id())
        if not AnswerTurn.run(start, debug, UiSession.reply_language(prompt)):
            messages.pop()
            return
        # Redraw from history (no agent call): the next turn then starts from exactly the layout it re-renders,
        # so no element of this run is left behind as a faded duplicate while the next answer is computed.
        st.rerun()
