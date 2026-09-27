import re

from smart_home_agent.answer_tags import _patterns


class CodeFences:
    """Splits an answer at its fenced code blocks, whose content is never parsed."""

    @staticmethod
    def split(text: str) -> list[tuple[str, bool]]:
        """(part, is_code) pairs in order; outside code, tags split over several lines are joined into one."""
        return [
            (part if i % 2 else _patterns.SPLIT_TAG.sub(lambda m: re.sub(r"\s+", " ", m[0]), part), i % 2 == 1)
            for i, part in enumerate(_patterns.FENCE.split(text))
            if part
        ]
