"""Search and filter contracts, plus the internal candidate structure."""

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from smart_home_agent.models.product import ProductSummary

SortOrder = Literal["price_asc", "price_desc", "completeness"]


class ProductFilter(BaseModel):
    """Exact structured criteria, evaluated in PostgreSQL. Values are canonical (already resolved)."""

    category: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    brands: list[str] = Field(default_factory=list)
    supports: list[str] = Field(default_factory=list)  # canonical compatibility ids, all must be supported
    product_type_contains: str | None = None
    product_ids: list[str] | None = None
    sort: SortOrder = "completeness"
    limit: int = Field(default=20, ge=1, le=500)

    @model_validator(mode="after")
    def _price_range(self) -> Self:
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price must not be greater than max_price")
        return self


class FilterResult(BaseModel):
    criteria: ProductFilter
    total: int
    products: list[ProductSummary]


class SearchHit(BaseModel):
    score: float
    product: ProductSummary


class SearchResult(BaseModel):
    query: str
    category: str | None
    hits: list[SearchHit]
    note: str = (
        "Semantic candidates only. Prices and titles come from PostgreSQL, but relevance is not a "
        "compatibility check: use check_compatibility before claiming compatibility."
    )


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    """A product id found by one retrieval path, before hydration from PostgreSQL."""

    product_id: str
    score: float | None
    source: Literal["semantic", "structured"]
