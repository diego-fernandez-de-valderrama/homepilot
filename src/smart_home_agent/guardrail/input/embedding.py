"""The embedding function the classifier uses: Gemini, CLASSIFICATION task type, L2-normalized."""

from collections.abc import Callable, Sequence
from itertools import batched

from catalog_ingestion.core import GeminiClient
from catalog_ingestion.indexing import GeminiEmbedder

# Gemini's CLASSIFICATION task type separated the categories clearly better than SEMANTIC_SIMILARITY in the
# tuning study (unseen test set: OFF_TOPIC 9/12 vs 0-5/12, no small talk with a blocking category on top).
TASK_TYPE = "CLASSIFICATION"

EmbedFn = Callable[[Sequence[str]], list[list[float]]]


def gemini_embed(client: GeminiClient, task_type: str = TASK_TYPE) -> EmbedFn:
    """Embedding function on the shared Gemini client (same model/dimension/retries as the catalog)."""

    def embed(texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for batch in batched(texts, GeminiEmbedder.BATCH_SIZE):
            vectors.extend(GeminiEmbedder.l2_normalize(v) for v in client.embed(list(batch), task_type=task_type))
        return vectors

    return embed
