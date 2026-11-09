from collections.abc import Sequence
from typing import Protocol

from smart_home_agent.models import Product, ProductFilter


class CatalogReader(Protocol):
    """What the services need from the structured catalog."""

    def get_products(self, product_ids: Sequence[str]) -> list[Product]: ...

    def get_product(self, product_id: str) -> Product | None: ...

    def filter_products(self, criteria: ProductFilter) -> tuple[int, list[Product]]: ...

    def get_versions(self, titles: Sequence[str]) -> dict[str, list[Product]]: ...
