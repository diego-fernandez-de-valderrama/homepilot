from enum import StrEnum


class Method(StrEnum):
    """How a fact was produced from its source."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"
