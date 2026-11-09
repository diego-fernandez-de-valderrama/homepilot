import queue
import time

from streamlit.delta_generator import DeltaGenerator

from smart_home_agent.agent import AgentReply
from smart_home_agent.ui.backend import TurnStarter
from smart_home_agent.ui.components import ProgressHtml


class TurnRunner:
    """Waits for one agent turn while showing real progress."""

    POLL_SECONDS = 0.15

    @staticmethod
    def run(start: TurnStarter, progress: DeltaGenerator) -> AgentReply:
        """Runs one turn (`start` submits it) and shows in `progress` a neutral typing cue, then a status line
        only for the tools the model actually calls (a plain "hi" never shows a catalog status). The caller then
        writes the answer into the same slot, so the live message has the same layout as the history one."""
        calls: queue.SimpleQueue[str] = queue.SimpleQueue()
        future = start(on_tool_call=calls.put)
        progress.html(ProgressHtml.TYPING)
        shown = None
        while not future.done():
            label = shown
            while not calls.empty():
                label = ProgressHtml.label_for(calls.get())
            if label is not None and label != shown:
                progress.html(ProgressHtml.progress(label))
                shown = label
            time.sleep(TurnRunner.POLL_SECONDS)
        return future.result()
