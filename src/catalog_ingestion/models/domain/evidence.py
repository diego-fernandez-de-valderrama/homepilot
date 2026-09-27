from dataclasses import dataclass

from catalog_ingestion.vocabulary import FactSource


@dataclass(frozen=True, slots=True)
class Evidence:
    source: FactSource
    text: str
    field: str | None = None  # e.g. "attributes.Unterstützte Systeme", "title", "description"
    url: str | None = None  # set for web evidence
