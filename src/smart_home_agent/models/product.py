"""Business models for products, mapped from the PostgreSQL catalog by the repository."""

from catalog_ingestion.domain.enums import Dimension, FactStatus, Necessity, RequirementKind
from pydantic import BaseModel

from smart_home_agent.models.evidence import Evidence, FieldProvenance

CAPABILITY_DIMENSIONS = (Dimension.ECOSYSTEM, Dimension.VOICE_ASSISTANT, Dimension.PROTOCOL)


class CompatibilityFact(BaseModel):
    dimension: Dimension
    canonical_value: str | None  # None when the raw value has no safe canonical mapping
    label: str | None
    raw_value: str
    status: FactStatus
    evidence: Evidence


class ProductRequirement(BaseModel):
    item: str
    canonical_item: str | None
    label: str
    kind: RequirementKind
    necessity: Necessity
    alternatives: list[str]  # canonical ids; any one of them satisfies the requirement
    evidence: Evidence


class Spec(BaseModel):
    name: str
    value: str
    unit: str | None = None


class ProductSummary(BaseModel):
    """Compact view used in lists (search, filter, recommendation)."""

    id: str
    title: str
    brand: str | None
    category: str | None
    category_label_en: str | None
    category_label_de: str | None
    product_type: str | None
    price: float | None
    currency: str | None
    original_price: float | None
    summary_en: str | None
    summary_de: str | None
    source_url: str | None


class Product(ProductSummary):
    """Full structured product. PostgreSQL is the source of truth for every field."""

    price_raw: str
    ean: str | None
    image_url: str | None
    is_smart_home: bool | None
    completeness_level: str
    completeness_score: float
    key_features: list[str]
    use_cases: list[str]
    specs: list[Spec]
    compatibility: list[CompatibilityFact]
    requirements: list[ProductRequirement]
    attributes: dict[str, dict[str, str]]  # original catalog attributes {section: {key: value}}
    provenance: list[FieldProvenance]
    validation_notes: list[str]

    def summary(self) -> ProductSummary:
        return ProductSummary.model_validate(self.model_dump(include=set(ProductSummary.model_fields)))

    def facts_for(self, canonical: str) -> list[CompatibilityFact]:
        return [fact for fact in self.compatibility if fact.canonical_value == canonical]

    def supported_values(self, dimensions: tuple[Dimension, ...] = CAPABILITY_DIMENSIONS) -> set[str]:
        """Canonical values with `supported` status and no contradicting `unsupported` fact."""
        supported = {
            f.canonical_value
            for f in self.compatibility
            if f.canonical_value and f.dimension in dimensions and f.status is FactStatus.SUPPORTED
        }
        unsupported = {f.canonical_value for f in self.compatibility if f.status is FactStatus.UNSUPPORTED}
        return supported - unsupported

    @property
    def requires_professional_installation(self) -> bool:
        return any(r.kind is RequirementKind.PROFESSIONAL_INSTALLATION for r in self.requirements)
