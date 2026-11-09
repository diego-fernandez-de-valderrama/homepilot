from pydantic import BaseModel

from smart_home_agent.models.comparison.types import RowGroup


class ComparisonRow(BaseModel):
    group: RowGroup
    attribute: str
    values: list[str]  # aligned with ComparisonResult.products; NOT_LISTED when the catalog has no value
    differs: bool
