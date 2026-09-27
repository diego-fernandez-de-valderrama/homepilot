"""Guardrail categories of a user message."""

from enum import StrEnum


class Category(StrEnum):
    SMART_HOME = "SMART_HOME"
    ELECTRICAL = "ELECTRICAL"
    OFF_TOPIC = "OFF_TOPIC"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    UNCERTAIN = "UNCERTAIN"


# Categories that can be answered deterministically instead of reaching the generative model. OFF_TOPIC is only
# blocked at input when AGENT_GUARDRAIL_INPUT_OFF_TOPIC=true; by default it is left to the agent's prompt and to the
# output check (see `GuardrailThresholds.block_off_topic`).
BLOCKING = frozenset({Category.ELECTRICAL, Category.OFF_TOPIC, Category.PROMPT_INJECTION})
