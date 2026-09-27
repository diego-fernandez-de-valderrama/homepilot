"""Prototype-based semantic classifier: Gemini embeddings + local cosine similarity, no training.

Startup: every prototype is embedded once (batched) and kept in memory.
Per message: one embedding call, then cosine similarity against the cached prototype vectors.
The category score is the mean of its `TOP_K` most similar prototypes, which is less sensitive to a
single accidental near-duplicate than the plain maximum.
"""

import logging
from collections.abc import Mapping, Sequence

from catalog_ingestion.indexing import GeminiEmbedder

from smart_home_agent.guardrail.input._decision_rule import decide
from smart_home_agent.guardrail.input.category import Category
from smart_home_agent.guardrail.input.decision import GuardrailDecision
from smart_home_agent.guardrail.input.embedding import EmbedFn
from smart_home_agent.guardrail.input.prototypes import PROTOTYPES
from smart_home_agent.guardrail.input.thresholds import GuardrailThresholds

logger = logging.getLogger(__name__)

TOP_K = 2


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
            cached[category].append(GeminiEmbedder.l2_normalize(vector))
        logger.info("guardrail: %d prototypes embedded for %d categories", len(texts), len(cached))
        return cls(embed, cached, thresholds)

    def classify(self, text: str) -> GuardrailDecision:
        """One embedding call + local similarity. Embedding errors propagate (callers fail open)."""
        return self.classify_vector(self._embed([text])[0], len(text.split()))

    def classify_vector(self, vector: Sequence[float], words: int | None = None) -> GuardrailDecision:
        return decide(self.scores(GeminiEmbedder.l2_normalize(list(vector))), self.thresholds, words)

    def scores(self, vector: Sequence[float]) -> dict[Category, float]:
        result = {}
        for category, prototypes in self._prototypes.items():
            similarities = sorted((self._cosine(vector, p) for p in prototypes), reverse=True)[:TOP_K]
            result[category] = sum(similarities) / len(similarities)
        return result

    @staticmethod
    def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))  # dot product: vectors are L2-normalized
