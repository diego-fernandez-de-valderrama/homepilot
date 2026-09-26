"""Embedding service, independent from parsing and enrichment."""

import math
from collections.abc import Sequence
from typing import Protocol

from catalog_ingestion.core.settings import GeminiSettings
from catalog_ingestion.llm.client import GeminiClient

BATCH_SIZE = 50


class Embedder(Protocol):
    @property
    def model_id(self) -> str:
        """Identifies model + dimension; a change forces re-embedding."""
        ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


class GeminiEmbedder:
    """Gemini embeddings. Truncated dimensions (< 3072) are L2-normalized, as Google recommends."""

    def __init__(self, client: GeminiClient, settings: GeminiSettings) -> None:
        self._client = client
        self._settings = settings

    @property
    def model_id(self) -> str:
        return f"{self._settings.embedding_model}@{self._settings.embedding_dim}"

    @property
    def dimension(self) -> int:
        return self._settings.embedding_dim

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = list(texts[start : start + BATCH_SIZE])
            vectors.extend(l2_normalize(v) for v in self._client.embed(batch, task_type="RETRIEVAL_DOCUMENT"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return l2_normalize(self._client.embed([text], task_type="RETRIEVAL_QUERY")[0])
