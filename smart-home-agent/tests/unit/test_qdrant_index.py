from typing import cast

from catalog_ingestion.indexing import Embedder
from qdrant_client import QdrantClient, models

from smart_home_agent.repositories import QdrantIndex


class _Embedder:
    model_id = "model-a@4"


def test_points_with_another_embedding_model_are_all_counted():
    client = QdrantClient(":memory:")
    client.create_collection("products", vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE))
    models_by_point = {1: "model-a@4", 2: "model-a@4", 3: "model-b@4", 4: None}
    client.upsert(
        "products",
        points=[
            models.PointStruct(id=pid, vector=[1.0, 0.0, 0.0, 0.0], payload={"embedding_model": model})
            for pid, model in models_by_point.items()
        ],
    )
    index = QdrantIndex(client, "products", cast(Embedder, _Embedder()))
    assert index.points_with_other_model() == 2
