from pydantic import BaseModel

from catalog_ingestion.models.schemas.compatibility_fact_schema import CompatibilityFactSchema
from catalog_ingestion.models.schemas.completeness_schema import CompletenessSchema
from catalog_ingestion.models.schemas.field_provenance_schema import FieldProvenanceSchema
from catalog_ingestion.models.schemas.normalized_product_schema import NormalizedProductSchema
from catalog_ingestion.models.schemas.price_schema import PriceSchema
from catalog_ingestion.models.schemas.requirement_schema import RequirementSchema
from catalog_ingestion.models.schemas.spec_out_schema import SpecOutSchema
from catalog_ingestion.models.schemas.web_info_schema import WebInfoSchema

SCHEMA_VERSION = 1  # bump on any contract change


# Output boundary: the enriched catalog product as stored in PostgreSQL (`products.document` JSONB)
# and read by the agent.
class CatalogProductSchema(BaseModel):
    schema_version: int = SCHEMA_VERSION
    id: str
    title: str
    brand: str | None
    category: str | None
    category_label_en: str | None
    category_label_de: str | None
    product_type: str | None
    is_smart_home: bool | None
    price: PriceSchema
    summary_en: str | None
    summary_de: str | None
    key_features: list[str]
    use_cases: list[str]
    specs: list[SpecOutSchema]
    compatibility: list[CompatibilityFactSchema]
    requirements: list[RequirementSchema]
    completeness: CompletenessSchema
    web: WebInfoSchema
    provenance: list[FieldProvenanceSchema]
    enrichment_model: str | None
    prompt_version: str | None
    validation_notes: list[str]
    normalized: NormalizedProductSchema
