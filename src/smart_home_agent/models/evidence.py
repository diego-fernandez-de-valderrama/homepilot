"""Provenance models: where a fact or a field value comes from."""

from catalog_ingestion.domain.enums import FactSource, Method
from pydantic import BaseModel


class Evidence(BaseModel):
    source: FactSource  # catalog | web | llm
    text: str
    field: str | None = None  # e.g. "attributes.Unterstützte Systeme", "title"
    url: str | None = None  # set for web evidence
    method: Method | None = None  # deterministic | llm
    confidence: float | None = None


class FieldProvenance(BaseModel):
    """Provenance of a descriptive field (summary, product type, specs, ...)."""

    field: str
    source: FactSource
    method: Method
    confidence: float
    detail: str | None = None


class EvidenceResult(BaseModel):
    product_id: str
    title: str
    topic: str
    items: list[Evidence]
    provenance: list[FieldProvenance]
    note: str | None = None
