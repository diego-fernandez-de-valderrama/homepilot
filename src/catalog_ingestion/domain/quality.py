from dataclasses import dataclass

from catalog_ingestion.domain.enums import CompletenessLevel


@dataclass(frozen=True, slots=True)
class CompletenessReport:
    score: float
    level: CompletenessLevel
    has_description: bool
    has_attributes: bool
    has_compatibility: bool
    needs_web: bool
    reasons: tuple[str, ...]
