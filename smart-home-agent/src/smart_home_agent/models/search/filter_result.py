from pydantic import BaseModel

from smart_home_agent.models.product import ProductSummary
from smart_home_agent.models.search.product_filter import ProductFilter


class FilterResult(BaseModel):
    criteria: ProductFilter
    total: int
    products: list[ProductSummary]
