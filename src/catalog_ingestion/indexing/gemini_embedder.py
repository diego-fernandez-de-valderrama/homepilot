import math
from collections.abc import Sequence

from catalog_ingestion.core import GeminiClient, GeminiSettings


class GeminiEmbedder:
    """Gemini embeddings. Truncated dimensions (< 3072) are L2-normalized, as Google recommends.

    Documents use the RETRIEVAL_DOCUMENT task type, queries RETRIEVAL_QUERY; the agent embeds its queries
    through this class, so both sides always match the index.
    """

    BATCH_SIZE = 50

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
        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = list(texts[start : start + self.BATCH_SIZE])
            vectors.extend(self.l2_normalize(v) for v in self._client.embed(batch, task_type="RETRIEVAL_DOCUMENT"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.l2_normalize(self._client.embed([text], task_type="RETRIEVAL_QUERY")[0])

    @staticmethod
    def l2_normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector
