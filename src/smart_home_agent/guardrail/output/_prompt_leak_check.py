"""prompt_leak: internal tool names or verbatim lines of the system instruction."""

from collections.abc import Sequence

from smart_home_agent.guardrail.output.violation import Violation


class PromptLeakCheck:
    def __init__(self, leak_markers: Sequence[str]) -> None:
        self._leak_markers = [m for m in leak_markers if m.strip()]

    def check(self, text: str) -> list[Violation]:
        folded = text.casefold()
        return [
            Violation(kind="prompt_leak", detail=marker[:80])
            for marker in self._leak_markers
            if marker.casefold() in folded
        ]
