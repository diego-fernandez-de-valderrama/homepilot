"""Prototype-based semantic classifier: Gemini embeddings + local cosine similarity, no training.

Startup: every prototype is embedded once (batched) and kept in memory.
Per message: one embedding call, then cosine similarity against the cached prototype vectors.
The category score is the mean of its `TOP_K` most similar prototypes, which is less sensitive to a
single accidental near-duplicate than the plain maximum.
"""

import logging
from collections.abc import Mapping, Sequence

import numpy as np
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
        self._prototypes = {
            category: np.asarray(vectors, dtype=np.float64) for category, vectors in prototype_vectors.items()
        }
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
        query = np.asarray(vector, dtype=np.float64)
        result = {}
        for category, prototypes in self._prototypes.items():
            similarities = prototypes @ query  # cosine: all vectors are L2-normalized
            result[category] = float(np.sort(similarities)[::-1][:TOP_K].mean())
        return result
