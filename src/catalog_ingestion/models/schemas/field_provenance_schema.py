from pydantic import BaseModel

from catalog_ingestion.vocabulary import FactSource, Method


class FieldProvenanceSchema(BaseModel):
    field: str
    source: FactSource
    method: Method
    confidence: float
    detail: str | None = None
