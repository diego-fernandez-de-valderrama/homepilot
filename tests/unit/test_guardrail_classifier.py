"""Decision rule of the prototype classifier, with synthetic vectors (no embeddings model)."""

from collections.abc import Sequence

import pytest

from smart_home_agent.guardrail.categories import Category
from smart_home_agent.guardrail.classifier import GuardrailThresholds, SemanticGuardrail, decide

THRESHOLDS = GuardrailThresholds(smart_home=0.8, electrical=0.85, off_topic=0.8, prompt_injection=0.8, margin=0.05)
AXES = {
    Category.SMART_HOME: [1.0, 0.0, 0.0, 0.0],
    Category.ELECTRICAL: [0.0, 1.0, 0.0, 0.0],
    Category.OFF_TOPIC: [0.0, 0.0, 1.0, 0.0],
    Category.PROMPT_INJECTION: [0.0, 0.0, 0.0, 1.0],
}


def scores(sh: float, el: float, ot: float = 0.1, pi: float = 0.1) -> dict[Category, float]:
    return {
        Category.SMART_HOME: sh,
        Category.ELECTRICAL: el,
        Category.OFF_TOPIC: ot,
        Category.PROMPT_INJECTION: pi,
    }


def test_confident_blocking_category_is_blocked():
    decision = decide(scores(sh=0.7, el=0.9), THRESHOLDS)
    assert decision.category is Category.ELECTRICAL and decision.blocked
    assert decision.margin == pytest.approx(0.2)


def test_below_category_threshold_is_uncertain_and_allowed():
    decision = decide(scores(sh=0.5, el=0.84), THRESHOLDS)
    assert decision.top_category is Category.ELECTRICAL
    assert decision.category is Category.UNCERTAIN and not decision.blocked


def test_small_margin_is_uncertain_and_allowed():
    decision = decide(scores(sh=0.88, el=0.9), THRESHOLDS)
    assert decision.category is Category.UNCERTAIN and not decision.blocked


def test_off_topic_needs_a_larger_margin_and_a_minimum_length():
    strict = THRESHOLDS.model_copy(update={"margin": 0.02, "off_topic_margin": 0.05, "off_topic_min_words": 3})
    assert decide(scores(sh=0.5, el=0.1, ot=0.84, pi=0.8), strict, words=5).category is Category.UNCERTAIN
    assert decide(scores(sh=0.5, el=0.1, ot=0.9, pi=0.8), strict, words=5).category is Category.OFF_TOPIC
    assert decide(scores(sh=0.5, el=0.1, ot=0.9, pi=0.8), strict, words=2).category is Category.UNCERTAIN
    # the stricter rules apply to OFF_TOPIC only
    assert decide(scores(sh=0.5, el=0.1, ot=0.1, pi=0.84), strict, words=2).category is Category.PROMPT_INJECTION


def test_off_topic_is_classified_but_only_blocked_when_enabled():
    decision = decide(scores(sh=0.5, el=0.1, ot=0.95, pi=0.1), THRESHOLDS, words=6)
    assert decision.category is Category.OFF_TOPIC and not decision.blocked
    enabled = THRESHOLDS.model_copy(update={"block_off_topic": True})
    assert decide(scores(sh=0.5, el=0.1, ot=0.95, pi=0.1), enabled, words=6).blocked


def test_smart_home_is_never_blocked():
    assert not decide(scores(sh=0.95, el=0.5), THRESHOLDS).blocked
    assert not decide(scores(sh=0.6, el=0.5), THRESHOLDS).blocked  # uncertain, still allowed


def test_prototypes_are_embedded_once_and_messages_once_each():
    calls: list[Sequence[str]] = []

    def embed(texts: Sequence[str]) -> list[list[float]]:
        calls.append(list(texts))
        return [AXES[Category.ELECTRICAL] if "wire" in t else AXES[Category.SMART_HOME] for t in texts]

    prototypes = {
        Category.SMART_HOME: ("thermostat for alexa", "smart plug"),
        Category.ELECTRICAL: ("wire it", "wire the switch"),
    }
    guardrail = SemanticGuardrail.create(embed, THRESHOLDS, prototypes)
    assert len(calls) == 1 and len(calls[0]) == 4  # one batched call at startup
    assert guardrail.classify("how do I wire this").category is Category.ELECTRICAL
    assert guardrail.classify("alexa thermostat").category is Category.SMART_HOME
    assert [len(c) for c in calls[1:]] == [1, 1]  # one embedding call per message


def test_score_is_mean_of_top_two_prototypes():
    vectors = {
        Category.SMART_HOME: [[1.0, 0.0], [0.6, 0.8], [0.0, 1.0]],
        Category.ELECTRICAL: [[0.0, 1.0]],
    }
    guardrail = SemanticGuardrail(lambda texts: [[1.0, 0.0]], vectors, THRESHOLDS)
    assert guardrail.scores([1.0, 0.0])[Category.SMART_HOME] == pytest.approx((1.0 + 0.6) / 2)


def test_thresholds_per_category():
    assert THRESHOLDS.for_category(Category.ELECTRICAL) == 0.85
    assert THRESHOLDS.for_category(Category.PROMPT_INJECTION) == 0.8
