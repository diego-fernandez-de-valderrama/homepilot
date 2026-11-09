"""Enumerations shared by the domain models, the boundary schemas, the database and the agent."""

from catalog_ingestion.vocabulary.enums.completeness_level import CompletenessLevel
from catalog_ingestion.vocabulary.enums.dimension import Dimension
from catalog_ingestion.vocabulary.enums.fact_source import FactSource
from catalog_ingestion.vocabulary.enums.fact_status import FactStatus
from catalog_ingestion.vocabulary.enums.method import Method
from catalog_ingestion.vocabulary.enums.necessity import Necessity
from catalog_ingestion.vocabulary.enums.requirement_kind import RequirementKind
from catalog_ingestion.vocabulary.enums.web_status import WebStatus

__all__ = [
    "CompletenessLevel",
    "Dimension",
    "FactSource",
    "FactStatus",
    "Method",
    "Necessity",
    "RequirementKind",
    "WebStatus",
]
