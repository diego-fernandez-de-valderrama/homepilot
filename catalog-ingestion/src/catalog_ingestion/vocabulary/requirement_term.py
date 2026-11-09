import re
from dataclasses import dataclass

from catalog_ingestion.vocabulary.enums import RequirementKind


@dataclass(frozen=True, slots=True)
class RequirementTerm:
    canonical: str
    label: str
    kind: RequirementKind
    pattern: re.Pattern[str]
