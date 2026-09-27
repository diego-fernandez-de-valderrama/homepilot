from catalog_ingestion.vocabulary import FactSource, Method
from pydantic import BaseModel


class Evidence(BaseModel):
    source: FactSource  # catalog | web | llm
    text: str
    field: str | None = None  # e.g. "attributes.Unterstützte Systeme", "title"
    url: str | None = None  # set for web evidence
    method: Method | None = None  # deterministic | llm
    confidence: float | None = None
