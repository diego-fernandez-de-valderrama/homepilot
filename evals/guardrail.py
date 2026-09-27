"""Guardrail evaluation (measurement only, nothing is trained).

uv run python -m evals guardrail             # metrics with the configured thresholds
uv run python -m evals guardrail --sweep     # plus score separation per category
uv run python -m evals guardrail --record    # also refresh the offline test fixture

Every text (prototypes, evaluation and acceptance cases) is embedded once; all metrics are then
computed locally from those vectors.
"""

import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from catalog_ingestion.llm.client import GeminiClient
from pydantic import BaseModel

from evals.guardrail_cases import ACCEPTANCE_CASES, EVAL_CASES, OUTPUT_CASES, TEST_CASES
from smart_home_agent.config import Settings
from smart_home_agent.container import guardrail_thresholds
from smart_home_agent.guardrail.categories import BLOCKING, Category, GuardrailDecision
from smart_home_agent.guardrail.classifier import (
    TASK_TYPE,
    GuardrailThresholds,
    SemanticGuardrail,
    blocked_categories,
    gemini_embed,
)
from smart_home_agent.guardrail.prototypes import PROTOTYPES

FIXTURE_PATH = Path("tests/fixtures/guardrail_embeddings.json")
ALLOWED = frozenset({Category.SMART_HOME, Category.UNCERTAIN})
LABELLED = (Category.SMART_HOME, Category.ELECTRICAL, Category.OFF_TOPIC, Category.PROMPT_INJECTION)


class EmbeddingFixture(BaseModel):
    """Recorded embeddings, so tests can run the real classifier offline."""

    model_id: str
    task_type: str
    vectors: dict[str, list[float]]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        missing = [t for t in texts if t not in self.vectors]
        if missing:
            raise KeyError(f"not in the embedding fixture (run `python -m evals guardrail --record`): {missing}")
        return [self.vectors[t] for t in texts]

    def guardrail(self, thresholds: GuardrailThresholds) -> SemanticGuardrail:
        vectors = {category: self.embed(texts) for category, texts in PROTOTYPES.items()}
        return SemanticGuardrail(self.embed, vectors, thresholds)

    @classmethod
    def load(cls, path: Path = FIXTURE_PATH) -> "EmbeddingFixture":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def is_correct(expected: Category, predicted: Category) -> bool:
    """UNCERTAIN as expectation means "must not be blocked"; UNCERTAIN as prediction is a miss otherwise."""
    return predicted in ALLOWED if expected is Category.UNCERTAIN else predicted is expected


def evaluate(
    guardrail: SemanticGuardrail, cases: Sequence[tuple[str, Category]]
) -> list[tuple[str, Category, GuardrailDecision]]:
    return [(text, expected, guardrail.classify(text)) for text, expected in cases]


def blockable(thresholds: GuardrailThresholds) -> frozenset[Category]:
    """Categories that are blocked at input with these settings (the classifier's own rule)."""
    return blocked_categories(thresholds)


def report(
    results: Sequence[tuple[str, Category, GuardrailDecision]], blocked_categories: frozenset[Category] = BLOCKING
) -> dict[str, float]:
    correct = sum(is_correct(expected, d.category) for _, expected, d in results)
    print(f"\nCases: {len(results)}   accuracy: {correct / len(results):.1%}")
    print(f"{'category':<18}{'precision':>10}{'recall':>8}{'support':>9}")
    metrics = {"accuracy": correct / len(results)}
    for category in LABELLED:
        predicted = [d.category is category for _, _, d in results]
        actual = [expected is category for _, expected, _ in results]
        tp = sum(p and a for p, a in zip(predicted, actual, strict=True))
        precision = tp / sum(predicted) if sum(predicted) else 1.0
        recall = tp / sum(actual) if sum(actual) else 1.0
        metrics[f"{category.value.lower()}_recall"] = recall
        print(f"{category.value:<18}{precision:>10.1%}{recall:>8.1%}{sum(actual):>9}")
    false_blocks = [(t, d) for t, e, d in results if e in ALLOWED and d.blocked]
    missed = [(t, e, d) for t, e, d in results if e in blocked_categories and not d.blocked]
    metrics["false_blocks"] = len(false_blocks)
    print(f"\nFalse blocks (allowed message blocked): {len(false_blocks)}")
    print(f"Missed blocks (reached the agent):      {len(missed)}")
    print("\nConfusion (expected -> predicted):")
    for (expected, predicted), count in sorted(Counter((e, d.category) for _, e, d in results).items()):
        print(f"  {expected.value:<17} -> {predicted.value:<17} {count}")
    wrong = [(t, e, d) for t, e, d in results if not is_correct(e, d.category)]
    if wrong:
        print("\nMisclassified:")
        for text, expected, d in wrong:
            print(
                f"  [{expected.value} -> {d.category.value}] top={d.top_category.value} {d.score:.3f} m={d.margin:.3f}"
            )
            print(f"      {text}")
    return metrics


def evaluate_output(guardrail: SemanticGuardrail) -> list[tuple[str, bool, GuardrailDecision]]:
    """The output check's domain decision (same classifier, applied to the model's answer)."""
    return [(text, off_topic, guardrail.classify(text)) for text, off_topic in OUTPUT_CASES]


def sweep(results: Sequence[tuple[str, Category, GuardrailDecision]]) -> None:
    """Score separation per blocking category: where a threshold can sit without blocking other messages."""
    print("\nScore separation (a threshold must stay above the highest score of other messages with that top):")
    for category in sorted(BLOCKING):
        positives = sorted(d.scores[category] for _, e, d in results if e is category)
        harmless = [d.scores[category] for _, e, d in results if e is not category and d.top_category is category]
        low = positives[0] if positives else float("nan")
        high = max(harmless) if harmless else float("nan")
        print(f"  {category.value:<17} positives min={low:.3f} median={positives[len(positives) // 2]:.3f}", end="")
        print(f"   highest other-labelled with this top category={high:.3f}")
    margins = sorted(d.margin for _, e, d in results if e in BLOCKING)
    print(f"  margins of blockable cases: min={margins[0]:.3f} p10={margins[len(margins) // 10]:.3f}")


def embed_all(settings: Settings) -> EmbeddingFixture:
    texts = list(
        dict.fromkeys(
            [
                *(t for texts in PROTOTYPES.values() for t in texts),
                *(t for t, _ in (*EVAL_CASES, *TEST_CASES, *ACCEPTANCE_CASES)),
                *(t for t, _ in OUTPUT_CASES),
            ]
        )
    )
    vectors = gemini_embed(GeminiClient(settings.gemini))(texts)
    model_id = f"{settings.gemini.embedding_model}@{settings.gemini.embedding_dim}"
    rounded = {t: [round(x, 5) for x in v] for t, v in zip(texts, vectors, strict=True)}
    return EmbeddingFixture(model_id=model_id, task_type=TASK_TYPE, vectors=rounded)


def run(settings: Settings, *, do_sweep: bool, record: bool) -> int:
    fixture = embed_all(settings)
    thresholds = guardrail_thresholds(settings.agent)
    print(f"Embedding model {fixture.model_id}, task type {fixture.task_type}")
    print(f"Thresholds {thresholds.model_dump()}")
    guardrail = fixture.guardrail(thresholds)
    print("\n=== Evaluation set (used for calibration) ===")
    blocked_categories = blockable(thresholds)
    print(f"Blocked at input: {', '.join(sorted(blocked_categories))} (OFF_TOPIC is always classified)")
    results = evaluate(guardrail, EVAL_CASES)
    report(results, blocked_categories)
    if do_sweep:
        sweep(results)
    print("\n=== Test set (never used for calibration) ===")
    report(evaluate(guardrail, TEST_CASES), blocked_categories)
    print("\n=== Output check: long answers without tools (OFF_TOPIC -> answer replaced) ===")
    output_results = evaluate_output(guardrail)
    for text, off_topic, d in output_results:
        flagged = d.category is Category.OFF_TOPIC
        mark = "ok " if flagged == off_topic else "BAD"
        print(
            f"  {mark} expected {'off-topic' if off_topic else 'in scope':<9} -> {d.category.value:<16} "
            f"{d.top_category.value} {d.score:.3f} m={d.margin:.3f}  {text[:60]}"
        )
    acceptance = evaluate(guardrail, ACCEPTANCE_CASES)
    print("\nAcceptance phrases:")
    for text, expected, d in acceptance:
        mark = "ok " if (d.blocked == (expected in blocked_categories)) else "BAD"
        print(f"  {mark} {d.category.value:<17} {d.score:.3f} m={d.margin:.3f}  {text}")
    if record:
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(json.dumps(fixture.model_dump(), separators=(",", ":")), encoding="utf-8")
        print(f"\nRecorded {len(fixture.vectors)} vectors to {FIXTURE_PATH}")
    return 0
