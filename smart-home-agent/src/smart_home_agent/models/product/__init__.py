"""Business models for products, mapped from the PostgreSQL catalog by the repository.

`ProductSummary` is the compact view used in lists; `Product` adds every structured fact (compatibility,
requirements, specs, provenance). Versions of one product (color, size, pack) share a title: `ProductVersion`
names one of them.
"""

from smart_home_agent.models.product.compatibility_fact import CompatibilityFact
from smart_home_agent.models.product.dimensions import CAPABILITY_DIMENSIONS, UPGRADE_DIMENSIONS
from smart_home_agent.models.product.product import Product
from smart_home_agent.models.product.product_requirement import ProductRequirement
from smart_home_agent.models.product.product_summary import ProductSummary
from smart_home_agent.models.product.product_version import ProductVersion
from smart_home_agent.models.product.spec import Spec

__all__ = [
    "CAPABILITY_DIMENSIONS",
    "UPGRADE_DIMENSIONS",
    "CompatibilityFact",
    "Product",
    "ProductRequirement",
    "ProductSummary",
    "ProductVersion",
    "Spec",
]
