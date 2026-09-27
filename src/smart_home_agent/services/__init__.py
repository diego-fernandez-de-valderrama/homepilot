"""Business logic between the tools and the repositories. Import everything from here:

    from smart_home_agent.services import RecommendationService, Vocabulary, ...

One subpackage per domain (one class per file, internals in `_modules`), listed bottom-up; each only uses the
ones above it:

- `vocabulary/`: free text -> canonical ids (`Vocabulary`, `ResolvedTerm`, `TermResolutionError`).
- `accessories/`: the catalog hub product for a required hub the customer may not own (`AccessoryService`).
- `retrieval/`: candidate discovery, Qdrant top-K and PostgreSQL matches (`RetrievalService`).
- `compatibility/`: supported / unsupported / unknown per requested term (`CompatibilityEvaluator` on one
  loaded product, `CompatibilityService` over the catalog). Unknown stays unknown.
- `recommendation/`: the `recommend_products` pipeline (`RecommendationService`): retrieval -> `HardFilter`
  -> compatibility gate -> `Ranker` -> `UpsellSelector` (+ accessories), one entry per product version family.
- `comparison/`: the 2-4 product table (`ComparisonService`, `ProductComparer`).
- `evidence/`: where a fact comes from (`EvidenceService`, `EvidenceLookup`).
- `rich_content/`: answer tags -> catalog data for the UI (`RichContentService`).
- `cart/`: cart views and all-or-nothing changes (`CartService`, `CentralUnit`).
- `profile/`: customer memory rules (`ProfileService`, `MemoryRuleError`).

`ProductNotFoundError` is shared: every service that reads products by id raises it.
"""

from smart_home_agent.services.accessories import AccessoryService
from smart_home_agent.services.cart import CartChangeError, CartService, CentralUnit, NotInCartError
from smart_home_agent.services.comparison import ComparisonService, ProductComparer
from smart_home_agent.services.compatibility import CompatibilityEvaluator, CompatibilityService
from smart_home_agent.services.evidence import EvidenceLookup, EvidenceService
from smart_home_agent.services.product_not_found_error import ProductNotFoundError
from smart_home_agent.services.profile import MemoryRuleError, ProfileService
from smart_home_agent.services.recommendation import (
    UPSELL_RULES,
    HardFilter,
    ProductType,
    Ranker,
    RankingCandidate,
    RecommendationService,
    UpsellSelector,
)
from smart_home_agent.services.retrieval import RetrievalService
from smart_home_agent.services.rich_content import RichContentService
from smart_home_agent.services.vocabulary import ResolvedTerm, TermResolutionError, Vocabulary

__all__ = [
    "UPSELL_RULES",
    "AccessoryService",
    "CartChangeError",
    "CartService",
    "CentralUnit",
    "ComparisonService",
    "CompatibilityEvaluator",
    "CompatibilityService",
    "EvidenceLookup",
    "EvidenceService",
    "HardFilter",
    "MemoryRuleError",
    "NotInCartError",
    "ProductComparer",
    "ProductNotFoundError",
    "ProductType",
    "ProfileService",
    "Ranker",
    "RankingCandidate",
    "RecommendationService",
    "ResolvedTerm",
    "RetrievalService",
    "RichContentService",
    "TermResolutionError",
    "UpsellSelector",
    "Vocabulary",
]
