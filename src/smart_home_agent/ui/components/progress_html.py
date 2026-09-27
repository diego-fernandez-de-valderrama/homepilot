from smart_home_agent.ui.components._templates import Templates
from smart_home_agent.ui.components._texts import TOOL_LABELS


class ProgressHtml:
    """What the live message shows while a turn runs: a typing cue, then the tool actually being called."""

    TYPING = Templates.render("progress", "typing")

    @staticmethod
    def label_for(tool_name: str) -> str:
        return TOOL_LABELS.get(tool_name, "Working on your request")

    @staticmethod
    def progress(label: str) -> str:
        return Templates.render("progress", "progress", label=label)
