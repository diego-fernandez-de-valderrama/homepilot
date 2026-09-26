"""LLM boundary: the structured output requested from Gemini (`response_schema`).

Nothing here is trusted: the validator checks every claim against the source texts.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from catalog_ingestion.domain.enums import Necessity, RequirementKind
from catalog_ingestion.vocabulary.categories import CATEGORY_KEYS

CategoryKey = StrEnum("CategoryKey", {key: key for key in CATEGORY_KEYS})

ClaimDimension = Literal["ecosystem", "voice_assistant", "protocol", "mobile_os"]
ClaimSource = Literal["catalog", "web"]


class SpecSchema(BaseModel):
    name: str = Field(description="Specification name in English, e.g. 'Battery life'.")
    value: str = Field(description="Value exactly as stated in the source, e.g. '5 Jahre' or '868,3 MHz'.")
    unit: str | None = Field(default=None, description="Unit if separable, e.g. 'MHz'.")


class CompatibilityClaimSchema(BaseModel):
    dimension: ClaimDimension
    value: str = Field(description="Name of the ecosystem, assistant, protocol or OS as written in the source.")
    status: Literal["supported", "unsupported"] = Field(
        description="'unsupported' only when the source explicitly says it does not work."
    )
    source: ClaimSource
    evidence_quote: str = Field(description="Verbatim quote from the cited source that states this claim.")


class RequirementClaimSchema(BaseModel):
    item: str = Field(description="What is required, e.g. 'Bosch Smart Home Controller'.")
    kind: RequirementKind
    necessity: Necessity
    alternatives: list[str] = Field(
        default_factory=list, description="Other items that satisfy the same requirement (OR), if stated."
    )
    source: ClaimSource
    evidence_quote: str = Field(description="Verbatim quote from the cited source that states this requirement.")


class LLMEnrichmentSchema(BaseModel):
    category: CategoryKey | None = Field(description="Best matching category key, or null if unclear.")
    product_type: str | None = Field(description="Short English product type, e.g. 'Door/window contact sensor'.")
    brand: str | None = Field(description="Manufacturer brand exactly as written in the title, or null.")
    summary_en: str | None = Field(description="2-3 factual English sentences based only on the sources.")
    summary_de: str | None = Field(description="The same summary in German.")
    key_features: list[str] = Field(description="Up to 8 short English feature phrases supported by the sources.")
    use_cases: list[str] = Field(description="Up to 6 short English use cases that follow from the product type.")
    specs: list[SpecSchema] = Field(description="Important technical specifications stated in the sources.")
    compatibility_claims: list[CompatibilityClaimSchema]
    requirements: list[RequirementClaimSchema]
