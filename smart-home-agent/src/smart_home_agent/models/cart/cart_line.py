from pydantic import BaseModel

from smart_home_agent.models.product import Product


class CartLine(BaseModel):
    product_id: str
    quantity: int
    product: Product | None  # None when the product is no longer in the active catalog
    unit_price: float | None
    line_total: float | None

    @property
    def available(self) -> bool:
        return self.product is not None
