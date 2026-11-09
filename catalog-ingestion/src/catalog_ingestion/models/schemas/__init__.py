"""Pydantic boundary contracts (everything that crosses a process or storage boundary):

- input: `RawProductSchema` (one JSON file of products.zip);
- LLM output: `LLMEnrichmentSchema` (Gemini `response_schema`) with `CompatibilityClaimSchema`,
  `RequirementClaimSchema`, `SpecSchema`;
- stored product: `CatalogProductSchema` (`products.document`, bump `SCHEMA_VERSION` on contract changes) and
  its parts (`NormalizedProductSchema`, `PriceSchema`, `CompatibilityFactSchema`, `RequirementSchema`, ...);
- Qdrant: `QdrantPayloadSchema`.
"""

from catalog_ingestion.models.schemas.attribute_schema import AttributeSchema
from catalog_ingestion.models.schemas.catalog_product_schema import SCHEMA_VERSION, CatalogProductSchema
from catalog_ingestion.models.schemas.compatibility_claim_schema import CompatibilityClaimSchema
from catalog_ingestion.models.schemas.compatibility_fact_schema import CompatibilityFactSchema
from catalog_ingestion.models.schemas.completeness_schema import CompletenessSchema
from catalog_ingestion.models.schemas.evidence_schema import EvidenceSchema
from catalog_ingestion.models.schemas.field_provenance_schema import FieldProvenanceSchema
from catalog_ingestion.models.schemas.key_value_schema import KeyValueSchema
from catalog_ingestion.models.schemas.llm_enrichment_schema import LLMEnrichmentSchema
from catalog_ingestion.models.schemas.normalized_product_schema import NormalizedProductSchema
from catalog_ingestion.models.schemas.price_schema import PriceSchema
from catalog_ingestion.models.schemas.qdrant_payload_schema import QdrantPayloadSchema
from catalog_ingestion.models.schemas.raw_product_schema import RawProductSchema
from catalog_ingestion.models.schemas.requirement_claim_schema import RequirementClaimSchema
from catalog_ingestion.models.schemas.requirement_schema import RequirementSchema
from catalog_ingestion.models.schemas.spec_out_schema import SpecOutSchema
from catalog_ingestion.models.schemas.spec_schema import SpecSchema
from catalog_ingestion.models.schemas.web_info_schema import WebInfoSchema

__all__ = [
    "SCHEMA_VERSION",
    "AttributeSchema",
    "CatalogProductSchema",
    "CompatibilityClaimSchema",
    "CompatibilityFactSchema",
    "CompletenessSchema",
    "EvidenceSchema",
    "FieldProvenanceSchema",
    "KeyValueSchema",
    "LLMEnrichmentSchema",
    "NormalizedProductSchema",
    "PriceSchema",
    "QdrantPayloadSchema",
    "RawProductSchema",
    "RequirementClaimSchema",
    "RequirementSchema",
    "SpecOutSchema",
    "SpecSchema",
    "WebInfoSchema",
]
