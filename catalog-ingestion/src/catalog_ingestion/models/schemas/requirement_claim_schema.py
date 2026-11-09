from pydantic import BaseModel, Field

from catalog_ingestion.models.schemas._claim_types import ClaimSource
from catalog_ingestion.vocabulary import Necessity, RequirementKind


class RequirementClaimSchema(BaseModel):
    item: str = Field(description="What is required, e.g. 'Bosch Smart Home Controller'.")
    kind: RequirementKind
    necessity: Necessity
    alternatives: list[str] = Field(
        default_factory=list, description="Other items that satisfy the same requirement (OR), if stated."
    )
    source: ClaimSource
    evidence_quote: str = Field(description="Verbatim quote from the cited source that states this requirement.")
