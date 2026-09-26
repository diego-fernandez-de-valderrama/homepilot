"""Web pages, LLM output and the final validated product."""

from dataclasses import dataclass
from datetime import datetime

from catalog_ingestion.domain.enums import (
    Dimension,
    FactSource,
    FactStatus,
    Method,
    Necessity,
    RequirementKind,
    WebStatus,
)
from catalog_ingestion.domain.facts import CompatibilityFact, Requirement
from catalog_ingestion.domain.product import NormalizedProduct
from catalog_ingestion.domain.quality import CompletenessReport


@dataclass(frozen=True, slots=True)
class WebPage:
    url: str
    ok: bool
    method: str | None  # "http" or "gemini_url_context"
    http_status: int | None
    text: str
    error: str | None
    fetched_at: datetime
    transient: bool = False  # failure that may succeed later (quota, timeout): never cached


@dataclass(frozen=True, slots=True)
class Spec:
    name: str
    value: str
    unit: str | None


@dataclass(frozen=True, slots=True)
class CompatibilityClaim:
    dimension: Dimension
    value: str
    status: FactStatus
    source: FactSource
    evidence_quote: str


@dataclass(frozen=True, slots=True)
class RequirementClaim:
    item: str
    kind: RequirementKind
    necessity: Necessity
    alternatives: tuple[str, ...]
    source: FactSource
    evidence_quote: str


@dataclass(frozen=True, slots=True)
class LLMEnrichment:
    """Unvalidated LLM output. Nothing in here is trusted until the validator accepts it."""

    category: str | None
    product_type: str | None
    brand: str | None
    summary_en: str | None
    summary_de: str | None
    key_features: tuple[str, ...]
    use_cases: tuple[str, ...]
    specs: tuple[Spec, ...]
    compatibility_claims: tuple[CompatibilityClaim, ...]
    requirement_claims: tuple[RequirementClaim, ...]


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    field: str
    source: FactSource
    method: Method
    confidence: float
    detail: str | None = None


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
