"""Hard constraints evaluated on PostgreSQL values (the same rules the repository applies in SQL)."""

from smart_home_agent.models.product import Product
from smart_home_agent.models.search import ProductFilter


def brand_matches(brand: str | None, wanted: list[str]) -> bool:
    if not wanted:
        return True
    if brand is None:
        return False
    value = brand.casefold()
    return any(value == w.strip().casefold() or value.startswith(f"{w.strip().casefold()} ") for w in wanted)


def rejection_reason(product: Product, criteria: ProductFilter) -> str | None:
    """Why a product fails the hard (non-compatibility) constraints, or None when it passes."""
    if criteria.category and product.category != criteria.category:
        return "category"
    if (criteria.min_price is not None or criteria.max_price is not None) and product.price is None:
        return "price_unknown"
    if criteria.min_price is not None and product.price is not None and product.price < criteria.min_price:
        return "price"
    if criteria.max_price is not None and product.price is not None and product.price > criteria.max_price:
        return "price"
    if not brand_matches(product.brand, criteria.brands):
        return "brand"
    return None
