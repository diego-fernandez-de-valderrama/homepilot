from pydantic import BaseModel

from smart_home_agent.models.product import ProductSummary


class SearchHit(BaseModel):
    score: float
    product: ProductSummary
