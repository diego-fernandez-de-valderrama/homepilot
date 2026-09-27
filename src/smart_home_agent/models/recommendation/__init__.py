"""Recommendation request and result. Compatibility gates the candidate set before any ranking.

`RecommendationRequest` -> `Recommendation`: `RankedProduct`s split into confirmed and unconfirmed (each with
its `VersionOption`s), at most one `UpsellSuggestion`, and accessories for required hubs.
"""

from smart_home_agent.models.recommendation.ranked_product import RankedProduct
from smart_home_agent.models.recommendation.recommendation import Recommendation
from smart_home_agent.models.recommendation.recommendation_request import RecommendationRequest
from smart_home_agent.models.recommendation.types import VersionStatus
from smart_home_agent.models.recommendation.upsell_suggestion import UpsellSuggestion
from smart_home_agent.models.recommendation.version_option import VersionOption

__all__ = [
    "RankedProduct",
    "Recommendation",
    "RecommendationRequest",
    "UpsellSuggestion",
    "VersionOption",
    "VersionStatus",
]
