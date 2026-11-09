from pydantic import BaseModel, Field

from smart_home_agent.models.compatibility import AccessorySuggestion
from smart_home_agent.models.recommendation.ranked_product import RankedProduct
from smart_home_agent.models.recommendation.recommendation_request import RecommendationRequest
from smart_home_agent.models.recommendation.upsell_suggestion import UpsellSuggestion


class Recommendation(BaseModel):
    request: RecommendationRequest
    best_match: str | None
    confirmed: list[RankedProduct]  # every requested term is supported
    unconfirmed: list[RankedProduct]  # at least one requested term is unknown (never recommended as compatible)
    excluded: dict[str, int]  # reason -> count (price, brand, category, unsupported, ...)
    upsell: UpsellSuggestion | None
    accessories: list[AccessorySuggestion] = Field(default_factory=list)  # required hubs for best match / upsell
    notes: list[str]
    # Why no confirmed candidate became the upsell (reason -> count), for the KPI eval; never sent to the model.
    upsell_blockers: dict[str, int] = Field(default_factory=dict, exclude=True)
