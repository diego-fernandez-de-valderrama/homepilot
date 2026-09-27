from pydantic import BaseModel, Field

from catalog_ingestion.models.schemas._claim_types import CategoryKey
from catalog_ingestion.models.schemas.compatibility_claim_schema import CompatibilityClaimSchema
from catalog_ingestion.models.schemas.requirement_claim_schema import RequirementClaimSchema
from catalog_ingestion.models.schemas.spec_schema import SpecSchema


# LLM boundary: the structured output requested from Gemini (`response_schema`).
#
# Nothing here is trusted: the validator checks every claim against the source texts.
# (A comment, not a docstring: Pydantic would put a docstring into the JSON schema.)
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
