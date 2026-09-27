from typing import Literal

from pydantic import BaseModel, Field

from catalog_ingestion.models.schemas._claim_types import ClaimDimension, ClaimSource


class CompatibilityClaimSchema(BaseModel):
    dimension: ClaimDimension
    value: str = Field(description="Name of the ecosystem, assistant, protocol or OS as written in the source.")
    status: Literal["supported", "unsupported"] = Field(
        description="'unsupported' only when the source explicitly says it does not work."
    )
    source: ClaimSource
    evidence_quote: str = Field(description="Verbatim quote from the cited source that states this claim.")
