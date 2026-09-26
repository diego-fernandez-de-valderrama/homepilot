"""Structured side-by-side comparison."""

from typing import Literal

from pydantic import BaseModel

from smart_home_agent.models.product import ProductSummary

NOT_LISTED = "not listed"

RowGroup = Literal["general", "compatibility", "requirements", "specs"]


class ComparisonRow(BaseModel):
    group: RowGroup
    attribute: str
    values: list[str]  # aligned with ComparisonResult.products; NOT_LISTED when the catalog has no value
    differs: bool


class ComparisonResult(BaseModel):
    products: list[ProductSummary]
    rows: list[ComparisonRow]
    key_features: dict[str, list[str]]  # product id -> features
    only_supported_by: dict[str, list[str]]  # product id -> capabilities no other compared product confirms
    notes: list[str]
