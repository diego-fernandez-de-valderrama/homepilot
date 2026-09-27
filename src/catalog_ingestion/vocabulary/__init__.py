"""The shared vocabulary: enumerations and canonical ids. Used by every other package and by the agent.
Import everything from here:

    from catalog_ingestion.vocabulary import CompatibilityVocabulary, Dimension, FactStatus, ...

- `enums/`: `Dimension`, `FactStatus`, `FactSource`, `Method`, `RequirementKind`, `Necessity`, `WebStatus`,
  `CompletenessLevel`.
- `CompatibilityVocabulary`: free text -> `CompatibilityTerm` (canonical id per dimension). Concepts never
  cross: Siri is not HomeKit, Google Assistant is not Google Home, Matter is not a protocol.
- `RequirementVocabulary`: requirement items (hubs, gateways, subscriptions, ...) -> `RequirementTerm`.
- `CategoryVocabulary`: URL category slug / category key -> `Category`.
- `BrandVocabulary`: the known brand at the start of a title.

The term tables themselves live in private `_modules`; add aliases only to existing canonical ids.
"""

from catalog_ingestion.vocabulary.brand_vocabulary import BrandVocabulary
from catalog_ingestion.vocabulary.category import Category
from catalog_ingestion.vocabulary.category_vocabulary import CategoryVocabulary
from catalog_ingestion.vocabulary.compatibility_term import CompatibilityTerm
from catalog_ingestion.vocabulary.compatibility_vocabulary import CompatibilityVocabulary
from catalog_ingestion.vocabulary.enums import (
    CompletenessLevel,
    Dimension,
    FactSource,
    FactStatus,
    Method,
    Necessity,
    RequirementKind,
    WebStatus,
)
from catalog_ingestion.vocabulary.requirement_term import RequirementTerm
from catalog_ingestion.vocabulary.requirement_vocabulary import RequirementVocabulary

__all__ = [
    "BrandVocabulary",
    "Category",
    "CategoryVocabulary",
    "CompatibilityTerm",
    "CompatibilityVocabulary",
    "CompletenessLevel",
    "Dimension",
    "FactSource",
    "FactStatus",
    "Method",
    "Necessity",
    "RequirementKind",
    "RequirementTerm",
    "RequirementVocabulary",
    "WebStatus",
]
