"""The classification of one message."""

from pydantic import BaseModel

from smart_home_agent.guardrail.input.category import Category


class GuardrailDecision(BaseModel):
    category: Category  # final decision (UNCERTAIN when below threshold or margin)
    top_category: Category  # best-scoring prototype category before the threshold/margin rule
    score: float  # similarity of the top category
    margin: float  # top score minus the second best category score
    scores: dict[Category, float]
    blocked: bool  # the message gets a deterministic reply instead of reaching the model
