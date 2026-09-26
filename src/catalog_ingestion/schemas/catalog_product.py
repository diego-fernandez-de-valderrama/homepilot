"""Output boundary: the enriched catalog product as stored in PostgreSQL (JSONB) and
served to the phase-2 agent."""

from pydantic import BaseModel, Field

from catalog_ingestion.domain.enums import (
    CompletenessLevel,
    Dimension,
    FactSource,
    FactStatus,
    Method,
    Necessity,
    RequirementKind,
    WebStatus,
)

SCHEMA_VERSION = 1


class PriceSchema(BaseModel):
    value: float | None
    currency: str | None
    original_value: float | None = None
    savings: float | None = None
    raw: str = ""


class KeyValueSchema(BaseModel):
    key: str
    value: str


class AttributeSchema(BaseModel):
    section: str
    key: str
    value: str


class NormalizedProductSchema(BaseModel):
    id: str
    title: str
    subtitle: str
    subtitle_features: list[str]
    subtitle_properties: list[KeyValueSchema]
    brand: str | None
    category_slug: str | None
    category: str | None
    price: PriceSchema
    variants: list[str]
    description_highlights: list[str]
    description_text: str
    badges: list[str]
    attributes: list[AttributeSchema]
    unparsed_attribute_lines: list[str]
    ean: str | None
    is_smart_home: bool | None
    image_url: str | None
    source_url: str | None


class EvidenceSchema(BaseModel):
    source: FactSource
    text: str
    field: str | None = None
    url: str | None = None


class CompatibilityFactSchema(BaseModel):
    dimension: Dimension
    raw_value: str
    canonical_value: str | None
    label: str | None = None
    status: FactStatus
    evidence: EvidenceSchema
    confidence: float = Field(ge=0.0, le=1.0)
    method: Method


class RequirementSchema(BaseModel):
    item: str
    canonical_item: str | None
    kind: RequirementKind
    necessity: Necessity
    alternatives: list[str]
    evidence: EvidenceSchema
    confidence: float = Field(ge=0.0, le=1.0)
    method: Method


class CompletenessSchema(BaseModel):
    score: float
    level: CompletenessLevel
    has_description: bool
    has_attributes: bool
    has_compatibility: bool
    needs_web: bool
    reasons: list[str]


class SpecOutSchema(BaseModel):
    name: str
    value: str
    unit: str | None = None


class FieldProvenanceSchema(BaseModel):
    field: str
    source: FactSource
    method: Method
    confidence: float
    detail: str | None = None


class WebInfoSchema(BaseModel):
    status: WebStatus
    url: str | None = None
    method: str | None = None


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
