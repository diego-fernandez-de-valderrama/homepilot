"""Guardrail categories and the decision model."""

from enum import StrEnum

from pydantic import BaseModel


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


class GuardrailDecision(BaseModel):
    category: Category  # final decision (UNCERTAIN when below threshold or margin)
    top_category: Category  # best-scoring prototype category before the threshold/margin rule
    score: float  # similarity of the top category
    margin: float  # top score minus the second best category score
    scores: dict[Category, float]
    blocked: bool  # the message gets a deterministic reply instead of reaching the model
