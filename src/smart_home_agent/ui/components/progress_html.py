import html

from smart_home_agent.ui.components._texts import TOOL_LABELS


class ProgressHtml:
    """What the live message shows while a turn runs: a typing cue, then the tool actually being called."""

    # Neutral "the advisor is writing" cue: no text, so it never claims work that is not happening.
    TYPING = (
        '<div class="hp-typing" role="status" aria-label="HomePilot is answering">'
        "<span></span><span></span><span></span></div>"
    )

    @staticmethod
    def label_for(tool_name: str) -> str:
        return TOOL_LABELS.get(tool_name, "Working on your request")

    @staticmethod
    def progress(label: str) -> str:
        return (
            '<div class="hp-progress" role="status"><span class="hp-progress__spinner"></span>'
            f"<span>{html.escape(label)}</span></div>"
        )
