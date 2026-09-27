"""Qdrant persistence. Point ids are derived from the stable dataset product id."""

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from catalog_ingestion.schemas.qdrant_payload import QdrantPayloadSchema

_NAMESPACE = uuid.UUID("0b6a1f2c-9d57-4a57-9a52-6c1e5b1f7a10")
UPSERT_BATCH = 128


_MAX_NUMERIC_ID = 2**63 - 1


def point_id(product_id: str) -> int | str:
    """Canonical numeric dataset ids are used directly; anything else maps to a stable UUIDv5.

    Only plain ASCII digits without a leading zero count as numeric, so "007" and "7" (or Unicode
    digits such as "²") never share or break a point id, and the value stays within Qdrant's range.
    """
    numeric = product_id.isascii() and product_id.isdigit() and not product_id.startswith("0")
    if numeric and int(product_id) <= _MAX_NUMERIC_ID:
        return int(product_id)
    return str(uuid.uuid5(_NAMESPACE, product_id))


@dataclass(frozen=True, slots=True)
class IndexedState:
    doc_hash: str | None
    embedding_model: str | None
    payload_hash: str | None = None


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
                with_payload=["product_id", "doc_hash", "embedding_model", "payload_hash"],
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                states[str(payload.get("product_id"))] = IndexedState(
                    payload.get("doc_hash"), payload.get("embedding_model"), payload.get("payload_hash")
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

    def overwrite_payloads(self, payloads: list[QdrantPayloadSchema]) -> None:
        """Replaces the payload of existing points without touching their vectors."""
        for start in range(0, len(payloads), UPSERT_BATCH):
            operations = [
                models.OverwritePayloadOperation(
                    overwrite_payload=models.SetPayload(
                        payload=payload.model_dump(mode="json"), points=[point_id(payload.product_id)]
                    )
                )
                for payload in payloads[start : start + UPSERT_BATCH]
            ]
            self._client.batch_update_points(self._collection, update_operations=operations, wait=True)

    def count_other_models(self, embedding_model: str) -> int:
        """Points embedded with a different model than `embedding_model` (or without one)."""
        other = models.Filter(
            must_not=[models.FieldCondition(key="embedding_model", match=models.MatchValue(value=embedding_model))]
        )
        return self._client.count(self._collection, count_filter=other, exact=True).count

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
