from pydantic import BaseModel

from smart_home_agent.models.product import Product


class CartChangeLine(BaseModel):
    """One product of a pending change, with its catalog data for the confirmation card."""

    product_id: str
    quantity: int | None  # None for remove: all units
    product: Product | None  # None when the id is not in the active catalog
    in_cart: int = 0  # units of this product in the cart when the change was proposed

    @property
    def units(self) -> int:
        """Units this line adds or removes."""
        return self.quantity if self.quantity is not None else self.in_cart
