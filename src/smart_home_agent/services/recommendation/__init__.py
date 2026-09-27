"""Recommendation pipeline, enforced in code (`RecommendationService.recommend`):

1. candidates: Qdrant top-K and PostgreSQL structured matches (`RetrievalService`);
2. hydrate them from PostgreSQL;
3. hard filters (`HardFilter`: category, price, brand);
4. compatibility gate (`CompatibilityEvaluator`): `confirmed` = every requested term supported, `unconfirmed` =
   some unknown, `unsupported` excluded;
5. price-neutral ranking (`Ranker`, `RankingCandidate`);
6. upselling (`UpsellSelector`) plus required-hub accessories (`AccessoryService`).

Only `confirmed` products can be the best match or the upsell. An upsell must not need a hub that the best
match does not need (its price difference would understate the real extra cost). Required hubs the customer
may not own are offered as accessories, from the catalog. `unconfirmed` products are returned separately so
the agent can mention them honestly.

Versions of one product (same title: another color, size or pack) take one slot, the best-ranked version.
The other versions are listed on that entry with their own result for the same request, and a version is
never the upsell of its own product (the capability difference between versions comes from gaps in the
catalog attributes, not from the product).
"""

from smart_home_agent.services.recommendation.hard_filter import HardFilter
from smart_home_agent.services.recommendation.product_type import ProductType
from smart_home_agent.services.recommendation.ranker import Ranker
from smart_home_agent.services.recommendation.ranking_candidate import RankingCandidate
from smart_home_agent.services.recommendation.recommendation_service import RecommendationService
from smart_home_agent.services.recommendation.upsell_selector import UPSELL_RULES, UpsellSelector

__all__ = [
    "UPSELL_RULES",
    "HardFilter",
    "ProductType",
    "Ranker",
    "RankingCandidate",
    "RecommendationService",
    "UpsellSelector",
]
