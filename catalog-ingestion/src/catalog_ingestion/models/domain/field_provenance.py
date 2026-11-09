from dataclasses import dataclass

from catalog_ingestion.vocabulary import FactSource, Method


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    field: str
    source: FactSource
    method: Method
    confidence: float
    detail: str | None = None
