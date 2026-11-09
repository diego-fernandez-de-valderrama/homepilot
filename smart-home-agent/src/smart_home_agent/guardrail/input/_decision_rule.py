"""Threshold + margin rule that turns per-category similarity scores into a decision."""

from collections.abc import Mapping

from smart_home_agent.guardrail.input.category import Category
from smart_home_agent.guardrail.input.decision import GuardrailDecision
from smart_home_agent.guardrail.input.thresholds import GuardrailThresholds


def decide(
    scores: Mapping[Category, float], thresholds: GuardrailThresholds, words: int | None = None
) -> GuardrailDecision:
    """Threshold + margin rule over per-category similarity scores (`words`: length of the message)."""
    ranked = sorted(scores.items(), key=lambda item: -item[1])
    (top, top_score), (_, second_score) = ranked[0], ranked[1]
    margin = top_score - second_score
    confident = top_score >= thresholds.for_category(top) and margin >= thresholds.margin_for(top)
    if top is Category.OFF_TOPIC and words is not None and words < thresholds.off_topic_min_words:
        confident = False
    category = top if confident else Category.UNCERTAIN
    return GuardrailDecision(
        category=category,
        blocked=category in thresholds.blocked_categories(),
        top_category=top,
        score=round(top_score, 4),
        margin=round(margin, 4),
        scores={category: round(score, 4) for category, score in ranked},
    )
