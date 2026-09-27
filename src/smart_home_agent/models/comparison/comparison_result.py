from pydantic import BaseModel

from smart_home_agent.models.comparison.comparison_row import ComparisonRow
from smart_home_agent.models.product import ProductSummary


class ComparisonResult(BaseModel):
    products: list[ProductSummary]
    rows: list[ComparisonRow]
    key_features: dict[str, list[str]]  # product id -> features
    only_supported_by: dict[str, list[str]]  # product id -> capabilities no other compared product confirms
    notes: list[str]
