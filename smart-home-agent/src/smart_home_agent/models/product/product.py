from catalog_ingestion.vocabulary import Dimension, FactStatus, RequirementKind

from smart_home_agent.models.evidence import FieldProvenance
from smart_home_agent.models.product.compatibility_fact import CompatibilityFact
from smart_home_agent.models.product.dimensions import CAPABILITY_DIMENSIONS
from smart_home_agent.models.product.product_requirement import ProductRequirement
from smart_home_agent.models.product.product_summary import ProductSummary
from smart_home_agent.models.product.product_version import ProductVersion
from smart_home_agent.models.product.spec import Spec

_HUB_KINDS = (RequirementKind.HUB, RequirementKind.GATEWAY)


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

    @property
    def runs_standalone(self) -> bool:
        """The catalog explicitly says the product also works without its hub ("standalone" alternative).
        A product without any hub requirement is unknown here, not stand-alone."""
        return any(r.kind in _HUB_KINDS and "standalone" in r.alternatives for r in self.requirements)
