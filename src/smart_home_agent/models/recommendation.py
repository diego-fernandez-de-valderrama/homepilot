"""Recommendation request and result. Compatibility gates the candidate set before any ranking."""

from typing import Literal, Self

from catalog_ingestion.domain.enums import FactStatus
from pydantic import BaseModel, Field, model_validator

from smart_home_agent.models.compatibility import AccessorySuggestion, TermCheck
from smart_home_agent.models.product import ProductSummary, ProductVersion


class RecommendationRequest(BaseModel):
    need: str = Field(min_length=1)
    category: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    brands: list[str] = Field(default_factory=list)
    must_support: list[str] = Field(default_factory=list)  # canonical compatibility ids (hard constraint)
    owned_devices: list[str] | None = None  # canonical requirement ids; None = not stated
    limit: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def _price_range(self) -> Self:
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price must not be greater than max_price")
        return self


VersionStatus = Literal["confirmed", "unconfirmed", "unsupported", "filtered_out"]


class VersionOption(ProductVersion):
    """Another version of a recommended product, with its own result for this request."""

    status: VersionStatus
    filter_reason: str | None = None  # the hard filter that removed it (price, brand, ...) when filtered_out


class RankedProduct(BaseModel):
    product: ProductSummary
    compatibility: FactStatus  # overall status for the requested terms
    checks: list[TermCheck]
    relevance: float
    score: float
    capabilities: list[str]  # labels of confirmed ecosystems, voice assistants and protocols
    missing_requirements: list[str]  # required hubs/gateways the user said they do not own
    unverified_requirements: list[str]  # required hubs/gateways; ownership not stated
    requires_professional_installation: bool
    other_versions: list[VersionOption] = Field(default_factory=list)  # same title, other color/size/pack


class UpsellSuggestion(BaseModel):
    product_id: str
    title: str
    variant: str | None = None  # the upsell's version label (color, size, pack), when it has one
    price: float
    base_product_id: str
    price_difference: float
    upgrade_reasons: list[str]  # factual, computed from structured data


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
