from pydantic import BaseModel

from catalog_ingestion.vocabulary import FactSource


class EvidenceSchema(BaseModel):
    source: FactSource
    text: str
    field: str | None = None
    url: str | None = None
