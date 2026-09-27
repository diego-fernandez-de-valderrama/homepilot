from typing import ClassVar

from qdrant_client import QdrantClient, models

from catalog_ingestion.core import QdrantSettings
from catalog_ingestion.indexing.collection_dimension_mismatch_error import CollectionDimensionMismatchError


class QdrantCollection:
    """Qdrant client and collection setup: vector config and payload indexes for filtering."""

    KEYWORD_FIELDS: ClassVar[tuple[str, ...]] = (
        "product_id",
        "brand",
        "category",
        "ecosystems",
        "voice_assistants",
        "protocols",
        "mobile_os",
        "requirements",
        "completeness_level",
    )
    FLOAT_FIELDS: ClassVar[tuple[str, ...]] = ("price",)
    BOOL_FIELDS: ClassVar[tuple[str, ...]] = ("is_smart_home", "requires_hub")

    @staticmethod
    def create_client(settings: QdrantSettings) -> QdrantClient:
        api_key = settings.api_key.get_secret_value() if settings.api_key else None
        return QdrantClient(url=settings.url, api_key=api_key, timeout=30)

    @staticmethod
    def ensure(client: QdrantClient, name: str, dimension: int, recreate: bool = False) -> None:
        """Creates the collection (idempotent); `recreate` drops an existing one first."""
        if client.collection_exists(name):
            if recreate:
                client.delete_collection(name)
            else:
                vectors = client.get_collection(name).config.params.vectors
                size = vectors.size if isinstance(vectors, models.VectorParams) else None
                if size != dimension:
                    raise CollectionDimensionMismatchError(
                        f"Qdrant collection '{name}' has dimension {size}, configured embedding dimension is "
                        f"{dimension}. Run `catalog-ingestion reindex --recreate`."
                    )
                return
        client.create_collection(
            name, vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE)
        )
        for field in QdrantCollection.KEYWORD_FIELDS:
            client.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)
        for field in QdrantCollection.FLOAT_FIELDS:
            client.create_payload_index(name, field, models.PayloadSchemaType.FLOAT)
        for field in QdrantCollection.BOOL_FIELDS:
            client.create_payload_index(name, field, models.PayloadSchemaType.BOOL)
