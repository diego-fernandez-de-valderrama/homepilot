"""Business models (Pydantic) and tool I/O of the agent. Import every model from here:

    from smart_home_agent.models import Product, RecommendationRequest, CartView

Flow, one subpackage per step:
1. `product/`: catalog products mapped from PostgreSQL (`Product`, `ProductSummary`), with provenance from
   `evidence/` (`Evidence`, `FieldProvenance`).
2. `search/`: exact filters (`ProductFilter` -> `FilterResult`) and semantic search (`SearchResult`).
3. `compatibility/`: one product checked against the customer's setup (`CompatibilityResult`).
4. `recommendation/`: `RecommendationRequest` -> `Recommendation` (ranked products, upsell, accessories).
5. `comparison/`: side-by-side comparison (`ComparisonResult`).
6. `cart/`: the shopping cart (`CartItem` in the session, `CartView` from the catalog, `CartConfirmation`).
7. `profile/`: the customer memory (`CustomerProfile`, `ProfileUpdate`).
8. `rich_content/`: catalog data for the answer's presentation tags (`RichContent`).
"""

from smart_home_agent.models.cart import (
    MAX_QUANTITY,
    CartAction,
    CartChange,
    CartChangeLine,
    CartConfirmation,
    CartItem,
    CartLine,
    CartView,
)
from smart_home_agent.models.comparison import NOT_LISTED, ComparisonResult, ComparisonRow, RowGroup
from smart_home_agent.models.compatibility import (
    AccessorySuggestion,
    CompatibilityResult,
    RequirementCheck,
    RequirementStatus,
    TermCheck,
)
from smart_home_agent.models.evidence import Evidence, EvidenceResult, FieldProvenance
from smart_home_agent.models.product import (
    CAPABILITY_DIMENSIONS,
    UPGRADE_DIMENSIONS,
    CompatibilityFact,
    Product,
    ProductRequirement,
    ProductSummary,
    ProductVersion,
    Spec,
)
from smart_home_agent.models.profile import (
    CustomerFact,
    CustomerProfile,
    CustomerSummary,
    FactKind,
    NewFact,
    ProfileUpdate,
    RejectedFact,
)
from smart_home_agent.models.recommendation import (
    RankedProduct,
    Recommendation,
    RecommendationRequest,
    UpsellSuggestion,
    VersionOption,
    VersionStatus,
)
from smart_home_agent.models.rich_content import ProductCompatibility, RichContent
from smart_home_agent.models.search import (
    FilterResult,
    ProductFilter,
    SearchCandidate,
    SearchHit,
    SearchResult,
    SortOrder,
)

__all__ = [
    "CAPABILITY_DIMENSIONS",
    "MAX_QUANTITY",
    "NOT_LISTED",
    "UPGRADE_DIMENSIONS",
    "AccessorySuggestion",
    "CartAction",
    "CartChange",
    "CartChangeLine",
    "CartConfirmation",
    "CartItem",
    "CartLine",
    "CartView",
    "ComparisonResult",
    "ComparisonRow",
    "CompatibilityFact",
    "CompatibilityResult",
    "CustomerFact",
    "CustomerProfile",
    "CustomerSummary",
    "Evidence",
    "EvidenceResult",
    "FactKind",
    "FieldProvenance",
    "FilterResult",
    "NewFact",
    "Product",
    "ProductCompatibility",
    "ProductFilter",
    "ProductRequirement",
    "ProductSummary",
    "ProductVersion",
    "ProfileUpdate",
    "RankedProduct",
    "Recommendation",
    "RecommendationRequest",
    "RejectedFact",
    "RequirementCheck",
    "RequirementStatus",
    "RichContent",
    "RowGroup",
    "SearchCandidate",
    "SearchHit",
    "SearchResult",
    "SortOrder",
    "Spec",
    "TermCheck",
    "UpsellSuggestion",
    "VersionOption",
    "VersionStatus",
]
