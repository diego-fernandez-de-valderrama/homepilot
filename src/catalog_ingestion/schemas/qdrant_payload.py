"""Output boundary: payload stored with each Qdrant point (used for filtering)."""

from pydantic import BaseModel


class QdrantPayloadSchema(BaseModel):
    product_id: str
    title: str
    brand: str | None
    category: str | None
    product_type: str | None
    price: float | None
    currency: str | None
    is_smart_home: bool | None
    ecosystems: list[str]
    voice_assistants: list[str]
    protocols: list[str]
    mobile_os: list[str]
    requirements: list[str]
    requires_hub: bool
    completeness_level: str
    image_url: str | None
    source_url: str | None
    doc_hash: str
    embedding_model: str
    # Hash of all other fields: a payload-only change (no re-embedding) is detected and overwritten.
    payload_hash: str | None = None
