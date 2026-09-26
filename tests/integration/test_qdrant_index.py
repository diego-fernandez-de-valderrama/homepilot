"""Qdrant queries without Gemini: an indexed point's own vector is used as the query."""

import pytest

from smart_home_agent.repositories.qdrant import QdrantIndex

pytestmark = pytest.mark.integration


class _NoEmbedder:
    model_id = "unused"
    dimension = 0

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("not used in this test")


def test_search_and_score_by_id(qdrant, settings):
    points, _ = qdrant.scroll(settings.qdrant.collection, limit=1, with_vectors=True, with_payload=True)
    point = points[0]
    product_id = str(point.payload["product_id"])
    index = QdrantIndex(qdrant, settings.qdrant.collection, _NoEmbedder())

    hits = index.search(point.vector, category=point.payload.get("category"), limit=5)
    assert hits[0].product_id == product_id
    assert hits[0].score == pytest.approx(1.0, abs=1e-3)
    assert index.score(point.vector, [product_id]) == {product_id: pytest.approx(1.0, abs=1e-3)}
    assert index.indexed_embedding_model()
