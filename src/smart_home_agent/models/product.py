"""Business models for products, mapped from the PostgreSQL catalog by the repository."""

from catalog_ingestion.domain.enums import Dimension, FactStatus, Necessity, RequirementKind
from pydantic import BaseModel, Field

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


class ProductVersion(BaseModel):
    """Another version of a product (same title): enough to name it and to offer it by id."""

    id: str
    variant: str | None
    subtitle: str | None
    price: float | None
    currency: str | None


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
    # Versions of one product (color, size, pack) share a title; these catalog strings tell them apart.
    subtitle: str | None = None
    variant: str | None = None  # this version's own option label, e.g. "Anthrazit", "2 Stk.", "806 lm"
    variant_options: list[str] = Field(default_factory=list)  # every option label the shop lists for the product

    @property
    def name(self) -> str:
        """Title plus this version's option label when it has one ("Access Point 2 (Anthrazit)")."""
        return f"{self.title} ({self.variant})" if self.variant else self.title


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

    def version(self) -> ProductVersion:
        return ProductVersion(
            id=self.id, variant=self.variant, subtitle=self.subtitle, price=self.price, currency=self.currency
        )

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
