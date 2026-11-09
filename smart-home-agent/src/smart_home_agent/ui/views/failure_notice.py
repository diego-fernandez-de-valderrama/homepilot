import streamlit as st

from smart_home_agent.ui.components import NoticeHtml


class FailureNotice:
    """A friendly notice instead of the answer; the technical detail only in developer mode (and the log)."""

    @staticmethod
    def show(language: str | None, debug: bool, detail: str | None) -> None:
        st.html(NoticeHtml.failure(language))
        if debug and detail:
            st.caption(f"Developer detail: {detail}")
