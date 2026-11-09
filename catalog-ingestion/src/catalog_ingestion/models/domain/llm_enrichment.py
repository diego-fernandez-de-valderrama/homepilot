from dataclasses import dataclass

from catalog_ingestion.models.domain.compatibility_claim import CompatibilityClaim
from catalog_ingestion.models.domain.requirement_claim import RequirementClaim
from catalog_ingestion.models.domain.spec import Spec


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
