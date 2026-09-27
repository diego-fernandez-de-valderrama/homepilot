from pydantic import BaseModel, Field

from smart_home_agent.models.cart.cart_change_line import CartChangeLine
from smart_home_agent.models.cart.types import MAX_QUANTITY, CartAction


class CartConfirmation(BaseModel):
    """A cart change the model asked for and the customer still has to confirm in the interface. One
    add_to_cart / remove_from_cart call can cover several products; they are confirmed together."""

    request_id: str  # id of ADK's confirmation request, answered by the confirmation turn
    action: CartAction
    lines: list[CartChangeLine] = Field(default_factory=list)

    def after(self, line: CartChangeLine) -> int:
        """Units of the line's product in the cart once this change is applied."""
        if self.action == "add":
            return min(line.in_cart + line.units, MAX_QUANTITY)
        return max(line.in_cart - line.units, 0)

    @property
    def total(self) -> float | None:
        """Price effect of the whole change (catalog prices), None when a line has no listed price."""
        prices = [line.product.price if line.product else None for line in self.lines]
        if not prices or any(price is None for price in prices):
            return None
        return round(sum(price * line.units for price, line in zip(prices, self.lines, strict=True) if price), 2)
