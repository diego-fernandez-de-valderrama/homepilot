import logging
from typing import Any

import streamlit as st

from smart_home_agent.ui.backend import CustomerDirectory, TurnStarter
from smart_home_agent.ui.components import ChromeHtml
from smart_home_agent.ui.page_assets import PageAssets
from smart_home_agent.ui.state import UiSession
from smart_home_agent.ui.turns.turn_runner import TurnRunner
from smart_home_agent.ui.views import AnswerView, ConfirmationCards, DebugPanel, FailureNotice

logger = logging.getLogger(__name__)


class AnswerTurn:
    """Runs a turn in a new assistant message and stores it in the history."""

    @staticmethod
    def run(start: TurnStarter, debug: bool, language: str | None) -> bool:
        """The model call is already retried silently (agent/model/), so a failure is shown as a friendly notice:
        - the turn ran but produced nothing to show (empty answer after all retries): stored in the history as a
          failed message, since its tools (e.g. a confirmed cart change) did run; returns True;
        - the backend raised: nothing is stored and False is returned, so the caller can offer a retry."""
        with st.chat_message("assistant", avatar=PageAssets.ADVISOR_AVATAR):
            st.html(ChromeHtml.assistant_eyebrow())
            answer = st.empty()  # progress first, then the answer, at the same position as in MessageView
            try:
                reply = TurnRunner.run(start, answer)
            except Exception as exc:  # the UI must survive backend failures (quota, network, database down)
                logger.exception("turn failed")
                with answer.container():
                    FailureNotice.show(language, debug, f"{type(exc).__name__}: {exc}")
                return False
            text = reply.text
            with answer.container():
                message: dict[str, Any] = {"role": "assistant", "content": text, "reply": reply}
                if reply.failed:
                    message |= {"failed": True, "language": reply.detected_language or language}
                    FailureNotice.show(message["language"], debug, reply.error or "empty answer")
                if text:
                    AnswerView.render(text, reply.rich)
                if reply.pending_confirmations:
                    ConfirmationCards.render(reply.pending_confirmations, interactive=True)
                if debug:
                    DebugPanel.render(reply)
        UiSession.messages().append(message)
        CustomerDirectory.refresh()  # the turn may have stored facts: the picker shows fresh counts
        return True
