from pydantic import BaseModel, Field

from smart_home_agent.models.cart.cart_line import CartLine


class CartView(BaseModel):
    lines: list[CartLine] = Field(default_factory=list)
    item_count: int = 0  # units, not lines
    total: float = 0.0  # available lines with a listed price only
    has_unpriced: bool = False  # some available line has no listed price (not in the total)

    def quantity_of(self, product_id: str) -> int:
        return next((line.quantity for line in self.lines if line.product_id == product_id), 0)

    def for_model(self) -> list[dict[str, object]]:
        """Compact lines for tool results: what the model needs to talk about the cart, nothing more."""
        return [
            {
                "product_id": line.product_id,
                "title": line.product.title if line.product else None,
                "variant": line.product.variant if line.product else None,  # tells versions of one product apart
                "subtitle": line.product.subtitle if line.product else None,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "line_total": line.line_total,
                "available": line.available,
            }
            for line in self.lines
        ]
