from catalog_ingestion.domain.enums import FactSource, Method
from pydantic import BaseModel


class FieldProvenance(BaseModel):
    """Provenance of a descriptive field (summary, product type, specs, ...)."""

    field: str
    source: FactSource
    method: Method
    confidence: float
    detail: str | None = None
