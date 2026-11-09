from pydantic import Field

from smart_home_agent.models._price_range import PriceRangeModel


class RecommendationRequest(PriceRangeModel):
    need: str = Field(min_length=1)
    category: str | None = None
    brands: list[str] = Field(default_factory=list)
    must_support: list[str] = Field(default_factory=list)  # canonical compatibility ids (hard constraint)
    owned_devices: list[str] | None = None  # canonical requirement ids; None = not stated
    limit: int = Field(default=5, ge=1, le=10)
