import streamlit as st

from smart_home_agent.ui.components import ChromeHtml, NoticeHtml
from smart_home_agent.ui.page_assets import PageAssets
from smart_home_agent.ui.views.answer_view import AnswerView
from smart_home_agent.ui.views.confirmation_cards import ConfirmationCards
from smart_home_agent.ui.views.debug_panel import DebugPanel
from smart_home_agent.ui.views.failure_notice import FailureNotice


class MessageView:
    """One message of the history (see `UiSession` for the message shapes)."""

    @staticmethod
    def render(message: dict, debug: bool, is_last: bool = False) -> None:
        """`is_last`: only the latest answer's cart changes can still be decided."""
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        elif message["role"] == "decision":
            with st.chat_message("user"):
                st.html(NoticeHtml.decision(message["confirmed"], message["cancelled"]))
        else:
            MessageView._assistant(message, debug, is_last)

    @staticmethod
    def _assistant(message: dict, debug: bool, is_last: bool) -> None:
        with st.chat_message("assistant", avatar=PageAssets.ADVISOR_AVATAR):
            st.html(ChromeHtml.assistant_eyebrow())
            reply = message.get("reply")
            if message.get("failed"):
                FailureNotice.show(message.get("language"), debug, reply.error if reply is not None else None)
            if message["content"]:
                AnswerView.render(message["content"], reply.rich if reply is not None else None)
            if reply is not None and reply.pending_confirmations:
                ConfirmationCards.render(reply.pending_confirmations, interactive=is_last)
            if debug and reply is not None:
                DebugPanel.render(reply)
