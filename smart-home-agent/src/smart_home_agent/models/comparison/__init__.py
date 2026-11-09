"""Structured side-by-side comparison: a `ComparisonResult` of aligned `ComparisonRow`s."""

from smart_home_agent.models.comparison.comparison_result import ComparisonResult
from smart_home_agent.models.comparison.comparison_row import ComparisonRow
from smart_home_agent.models.comparison.types import NOT_LISTED, RowGroup

__all__ = ["NOT_LISTED", "ComparisonResult", "ComparisonRow", "RowGroup"]
