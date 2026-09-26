"""Semantic retrieval over the Qdrant collection built by `catalog-ingestion`.

Queries are embedded with the same `GeminiEmbedder` (model, dimension, RETRIEVAL_QUERY task type,
L2 normalization) that produced the indexed document vectors. Only product ids and scores leave
this module: the payload is never used as a source of truth.
"""

from collections.abc import Sequence
from typing import Protocol

from catalog_ingestion.retrieval.embeddings import Embedder
from catalog_ingestion.storage.qdrant.repository import point_id
from qdrant_client import QdrantClient, models

from smart_home_agent.models.search import SearchCandidate


class SemanticIndex(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def search(self, vector: list[float], category: str | None, limit: int) -> list[SearchCandidate]: ...

    def score(self, vector: list[float], product_ids: Sequence[str]) -> dict[str, float]: ...


class QdrantIndex:
    def __init__(self, client: QdrantClient, collection: str, embedder: Embedder) -> None:
        self._client = client
        self._collection = collection
        self._embedder = embedder

    def embed(self, text: str) -> list[float]:
        return self._embedder.embed_query(text)

    def search(self, vector: list[float], category: str | None, limit: int) -> list[SearchCandidate]:
        """Nearest products. The optional category pre-filter only improves recall; PostgreSQL re-checks it."""
        query_filter = (
            models.Filter(must=[models.FieldCondition(key="category", match=models.MatchValue(value=category))])
            if category
            else None
        )
        response = self._client.query_points(
            self._collection, query=vector, limit=limit, query_filter=query_filter, with_payload=["product_id"]
        )
        return [
            SearchCandidate(product_id=str((p.payload or {}).get("product_id")), score=p.score, source="semantic")
            for p in response.points
        ]

    def score(self, vector: list[float], product_ids: Sequence[str]) -> dict[str, float]:
        """Similarity of the query to specific products (for candidates found by the structured path)."""
        if not product_ids:
            return {}
        response = self._client.query_points(
            self._collection,
            query=vector,
            limit=len(product_ids),
            query_filter=models.Filter(must=[models.HasIdCondition(has_id=[point_id(pid) for pid in product_ids])]),
            with_payload=["product_id"],
        )
        return {str((p.payload or {}).get("product_id")): p.score for p in response.points}

    def count(self) -> int:
        return self._client.count(self._collection, exact=True).count

    def indexed_embedding_model(self) -> str | None:
        """Embedding model id stored with an indexed point (to detect a model/dimension mismatch)."""
        points, _ = self._client.scroll(self._collection, limit=1, with_payload=["embedding_model"])
        return (points[0].payload or {}).get("embedding_model") if points else None

    @property
    def query_embedding_model(self) -> str:
        return self._embedder.model_id
