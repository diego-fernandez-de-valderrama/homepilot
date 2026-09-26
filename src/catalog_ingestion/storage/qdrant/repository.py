"""Qdrant persistence. Point ids are derived from the stable dataset product id."""

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from catalog_ingestion.schemas.qdrant_payload import QdrantPayloadSchema

_NAMESPACE = uuid.UUID("0b6a1f2c-9d57-4a57-9a52-6c1e5b1f7a10")
UPSERT_BATCH = 128


def point_id(product_id: str) -> int | str:
    """Numeric dataset ids are used directly; anything else maps to a stable UUIDv5."""
    return int(product_id) if product_id.isdigit() else str(uuid.uuid5(_NAMESPACE, product_id))


@dataclass(frozen=True, slots=True)
class IndexedState:
    doc_hash: str | None
    embedding_model: str | None


@dataclass(frozen=True, slots=True)
class SearchHit:
    product_id: str
    score: float
    payload: dict


class QdrantRepository:
    def __init__(self, client: QdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    def indexed_states(self, product_ids: list[str]) -> dict[str, IndexedState]:
        states: dict[str, IndexedState] = {}
        for start in range(0, len(product_ids), 256):
            chunk = product_ids[start : start + 256]
            records = self._client.retrieve(
                self._collection,
                ids=[point_id(pid) for pid in chunk],
                with_payload=["product_id", "doc_hash", "embedding_model"],
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                states[str(payload.get("product_id"))] = IndexedState(
                    payload.get("doc_hash"), payload.get("embedding_model")
                )
        return states

    def upsert(self, items: list[tuple[QdrantPayloadSchema, list[float]]]) -> None:
        for start in range(0, len(items), UPSERT_BATCH):
            points = [
                models.PointStruct(
                    id=point_id(payload.product_id), vector=vector, payload=payload.model_dump(mode="json")
                )
                for payload, vector in items[start : start + UPSERT_BATCH]
            ]
            self._client.upsert(self._collection, points=points, wait=True)

    def delete(self, product_ids: list[str]) -> None:
        if product_ids:
            self._client.delete(
                self._collection,
                points_selector=models.PointIdsList(points=[point_id(pid) for pid in product_ids]),
                wait=True,
            )

    def count(self) -> int:
        return self._client.count(self._collection, exact=True).count

    def search(self, vector: list[float], limit: int = 5, query_filter: models.Filter | None = None) -> list[SearchHit]:
        response = self._client.query_points(
            self._collection, query=vector, limit=limit, query_filter=query_filter, with_payload=True
        )
        return [
            SearchHit(product_id=str((p.payload or {}).get("product_id")), score=p.score, payload=p.payload or {})
            for p in response.points
        ]
