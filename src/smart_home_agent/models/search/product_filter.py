from pydantic import Field

from smart_home_agent.models._price_range import PriceRangeModel
from smart_home_agent.models.search.types import SortOrder


class ProductFilter(PriceRangeModel):
    """Exact structured criteria, evaluated in PostgreSQL. Values are canonical (already resolved)."""

    category: str | None = None
    brands: list[str] = Field(default_factory=list)
    supports: list[str] = Field(default_factory=list)  # canonical compatibility ids, all must be supported
    product_type_contains: str | None = None
    product_ids: list[str] | None = None
    sort: SortOrder = "completeness"
    limit: int = Field(default=20, ge=1, le=500)
