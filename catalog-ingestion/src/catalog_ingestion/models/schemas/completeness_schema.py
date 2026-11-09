from pydantic import BaseModel

from catalog_ingestion.vocabulary import CompletenessLevel


class CompletenessSchema(BaseModel):
    score: float
    level: CompletenessLevel
    has_description: bool
    has_attributes: bool
    has_compatibility: bool
    needs_web: bool
    reasons: list[str]
