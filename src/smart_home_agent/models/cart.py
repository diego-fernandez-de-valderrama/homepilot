"""Shopping cart models. The session stores only ids and quantities; everything shown about a cart line
(title, price, image) is read from PostgreSQL when the cart is viewed."""

from typing import Literal

from pydantic import BaseModel, Field

from smart_home_agent.models.product import Product

MAX_QUANTITY = 99

CartAction = Literal["add", "remove"]


class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=MAX_QUANTITY)


class CartLine(BaseModel):
    product_id: str
    quantity: int
    product: Product | None  # None when the product is no longer in the active catalog
    unit_price: float | None
    line_total: float | None

    @property
    def available(self) -> bool:
        return self.product is not None


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


class CartChange(BaseModel):
    """One product of an add/remove call: units to add or remove (None for remove: all units)."""

    product_id: str
    quantity: int | None


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
