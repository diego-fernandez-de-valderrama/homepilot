from dataclasses import dataclass

from catalog_ingestion.models import CompatibilityFact, CompletenessReport, NormalizedProduct, RawProduct, Requirement


@dataclass(frozen=True, slots=True)
class PreparedProduct:
    """A product after the deterministic stages, ready for enrichment."""

    raw: RawProduct
    raw_hash: str
    product: NormalizedProduct
    facts: tuple[CompatibilityFact, ...]
    requirements: tuple[Requirement, ...]
    completeness: CompletenessReport
