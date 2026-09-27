"""Structured comparison of 2-4 products using PostgreSQL data only (never retrieved text).

ComparisonService(catalog).compare(ids)      # validates the ids, reads the catalog
ProductComparer.compare(products)            # pure table building, also used for <compare> tags
"""

from smart_home_agent.services.comparison.comparison_service import ComparisonService
from smart_home_agent.services.comparison.product_comparer import ProductComparer

__all__ = ["ComparisonService", "ProductComparer"]
