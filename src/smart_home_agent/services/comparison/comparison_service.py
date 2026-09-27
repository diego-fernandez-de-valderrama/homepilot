from collections.abc import Sequence

from smart_home_agent.models import ComparisonResult
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services.comparison.product_comparer import ProductComparer
from smart_home_agent.services.product_not_found_error import ProductNotFoundError


class ComparisonService:
    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog

    def compare(self, product_ids: Sequence[str]) -> ComparisonResult:
        ids = list(dict.fromkeys(product_ids))
        low, high = ProductComparer.MIN_PRODUCTS, ProductComparer.MAX_PRODUCTS
        if not low <= len(ids) <= high:
            raise ValueError(f"compare between {low} and {high} distinct products")
        products = self._catalog.get_products(ids)
        missing = [pid for pid in ids if pid not in {p.id for p in products}]
        if missing:
            raise ProductNotFoundError(missing)
        return ProductComparer.compare(products)
