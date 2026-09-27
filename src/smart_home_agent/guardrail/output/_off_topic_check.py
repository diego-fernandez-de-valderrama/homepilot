"""off_topic: only for long answers produced without any tool, one embedding call against the prototypes."""

import logging

from smart_home_agent.guardrail.input import Category, SemanticGuardrail
from smart_home_agent.guardrail.output.violation import Violation

logger = logging.getLogger(__name__)


class OffTopicCheck:
    def __init__(self, guardrail: SemanticGuardrail | None, min_chars: int) -> None:
        self._guardrail = guardrail
        self._min_chars = min_chars

    def check(self, text: str) -> list[Violation]:
        if self._guardrail is None or len(text) < self._min_chars:
            return []
        try:
            decision = self._guardrail.classify(text)
        except Exception:
            logger.warning("output check: domain embedding failed, check skipped", exc_info=True)
            return []
        if decision.category is Category.OFF_TOPIC:
            return [Violation(kind="off_topic", detail=f"score={decision.score}")]
        return []
