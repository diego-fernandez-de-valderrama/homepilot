from dataclasses import dataclass

from catalog_ingestion.models.domain.compatibility_fact import CompatibilityFact
from catalog_ingestion.models.domain.completeness_report import CompletenessReport
from catalog_ingestion.models.domain.field_provenance import FieldProvenance
from catalog_ingestion.models.domain.normalized_product import NormalizedProduct
from catalog_ingestion.models.domain.requirement import Requirement
from catalog_ingestion.models.domain.spec import Spec
from catalog_ingestion.vocabulary import Dimension, FactStatus, WebStatus


@dataclass(frozen=True, slots=True)
class EnrichedProduct:
    product: NormalizedProduct
    completeness: CompletenessReport
    category: str | None
    product_type: str | None
    brand: str | None
    summary_en: str | None
    summary_de: str | None
    key_features: tuple[str, ...]
    use_cases: tuple[str, ...]
    specs: tuple[Spec, ...]
    compatibility: tuple[CompatibilityFact, ...]
    requirements: tuple[Requirement, ...]
    provenance: tuple[FieldProvenance, ...]
    web_status: WebStatus
    web_url: str | None
    web_method: str | None
    enrichment_model: str | None
    prompt_version: str | None
    validation_notes: tuple[str, ...]

    @property
    def id(self) -> str:
        return self.product.id

    def supported(self, dimension: Dimension) -> tuple[str, ...]:
        """Canonical values with `supported` status for a dimension, in stable order."""
        values = {
            fact.canonical_value
            for fact in self.compatibility
            if fact.dimension is dimension and fact.status is FactStatus.SUPPORTED and fact.canonical_value
        }
        return tuple(sorted(values))
