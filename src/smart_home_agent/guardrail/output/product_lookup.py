"""The only catalog access the output checks need."""

from collections.abc import Sequence
from typing import Protocol

from smart_home_agent.models.product import Product


class ProductLookup(Protocol):
    """The only catalog access the output check needs: which of these ids exist."""

    def get_products(self, product_ids: Sequence[str]) -> Sequence[Product]: ...
