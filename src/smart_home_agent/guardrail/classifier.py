"""Prototype-based semantic classifier: Gemini embeddings + local cosine similarity, no training.

Startup: every prototype is embedded once (batched) and kept in memory.
Per message: one embedding call, then cosine similarity against the cached prototype vectors.
The category score is the mean of its `TOP_K` most similar prototypes, which is less sensitive to a
single accidental near-duplicate than the plain maximum.
"""

import logging
from collections.abc import Callable, Mapping, Sequence

from catalog_ingestion.llm.client import GeminiClient
from catalog_ingestion.retrieval.embeddings import BATCH_SIZE, l2_normalize
from pydantic import BaseModel, Field

from smart_home_agent.guardrail.categories import BLOCKING, Category, GuardrailDecision
from smart_home_agent.guardrail.prototypes import PROTOTYPES

logger = logging.getLogger(__name__)

# Gemini's CLASSIFICATION task type separated the categories clearly better than SEMANTIC_SIMILARITY in the
# tuning study (unseen test set: OFF_TOPIC 9/12 vs 0-5/12, no small talk with a blocking category on top).
TASK_TYPE = "CLASSIFICATION"
TOP_K = 2

EmbedFn = Callable[[Sequence[str]], list[list[float]]]


class GuardrailThresholds(BaseModel):
    """Minimum similarity per category and minimum distance to the runner-up category.

    Below the threshold, or closer than `margin` to the second category, the decision is UNCERTAIN
    and the message goes to the agent: an ambiguous message is never blocked.

    OFF_TOPIC needs more evidence than the other blocking categories. Short, content-free messages
    ("hmm", "I'm Diego") score about 0.77-0.84 against every category, right where off-topic requests
    start, and a missed off-topic message is cheap (the agent's prompt still redirects it) while a
    wrongly blocked small-talk message breaks the conversation.
    """

    smart_home: float = Field(ge=0.0, le=1.0)
    electrical: float = Field(ge=0.0, le=1.0)
    off_topic: float = Field(ge=0.0, le=1.0)
    prompt_injection: float = Field(ge=0.0, le=1.0)
    margin: float = Field(ge=0.0, le=1.0)
    off_topic_margin: float = Field(default=0.0, ge=0.0, le=1.0)  # effective margin: max(margin, this)
    off_topic_min_words: int = Field(default=0, ge=0)  # shorter messages are never OFF_TOPIC
    # OFF_TOPIC is still classified (for the output check and the developer panel) but only blocks when true.
    block_off_topic: bool = False

    def for_category(self, category: Category) -> float:
        return getattr(self, category.value.lower())

    def margin_for(self, category: Category) -> float:
        return max(self.margin, self.off_topic_margin) if category is Category.OFF_TOPIC else self.margin


def gemini_embed(client: GeminiClient, task_type: str = TASK_TYPE) -> EmbedFn:
    """Embedding function on the shared Gemini client (same model/dimension/retries as the catalog)."""

    def embed(texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = list(texts[start : start + BATCH_SIZE])
            vectors.extend(l2_normalize(v) for v in client.embed(batch, task_type=task_type))
        return vectors

    return embed


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))  # cosine: vectors are L2-normalized


def word_count(text: str) -> int:
    return len(text.split())


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
    blocking = BLOCKING if thresholds.block_off_topic else BLOCKING - {Category.OFF_TOPIC}
    return GuardrailDecision(
        category=category,
        blocked=category in blocking,
        top_category=top,
        score=round(top_score, 4),
        margin=round(margin, 4),
        scores={category: round(score, 4) for category, score in ranked},
    )


class SemanticGuardrail:
    def __init__(
        self,
        embed: EmbedFn,
        prototype_vectors: Mapping[Category, Sequence[Sequence[float]]],
        thresholds: GuardrailThresholds,
    ) -> None:
        self._embed = embed
        self._prototypes = {category: [list(v) for v in vectors] for category, vectors in prototype_vectors.items()}
        self.thresholds = thresholds

    @classmethod
    def create(
        cls,
        embed: EmbedFn,
        thresholds: GuardrailThresholds,
        prototypes: Mapping[Category, Sequence[str]] = PROTOTYPES,
    ) -> "SemanticGuardrail":
        """Embeds all prototypes once (batched) and caches them in memory."""
        texts = [(category, text) for category, examples in prototypes.items() for text in examples]
        vectors = embed([text for _, text in texts])
        cached: dict[Category, list[list[float]]] = {category: [] for category in prototypes}
        for (category, _), vector in zip(texts, vectors, strict=True):
            cached[category].append(l2_normalize(vector))
        logger.info("guardrail: %d prototypes embedded for %d categories", len(texts), len(cached))
        return cls(embed, cached, thresholds)

    def scores(self, vector: Sequence[float]) -> dict[Category, float]:
        result = {}
        for category, prototypes in self._prototypes.items():
            similarities = sorted((_dot(vector, p) for p in prototypes), reverse=True)[:TOP_K]
            result[category] = sum(similarities) / len(similarities)
        return result

    def classify_vector(self, vector: Sequence[float], words: int | None = None) -> GuardrailDecision:
        return decide(self.scores(l2_normalize(list(vector))), self.thresholds, words)

    def classify(self, text: str) -> GuardrailDecision:
        """One embedding call + local similarity. Embedding errors propagate (callers fail open)."""
        return self.classify_vector(self._embed([text])[0], word_count(text))
