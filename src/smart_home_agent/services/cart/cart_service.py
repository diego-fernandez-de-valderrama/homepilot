from collections.abc import Mapping, Sequence
from typing import Any

from smart_home_agent.models import (
    MAX_QUANTITY,
    CartAction,
    CartChange,
    CartChangeLine,
    CartConfirmation,
    CartItem,
    CartLine,
    CartView,
    ProductSummary,
)
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services.cart._change_parser import parse_changes
from smart_home_agent.services.cart._quantity import parse_quantity
from smart_home_agent.services.cart.cart_change_error import CartChangeError
from smart_home_agent.services.cart.central_unit import CentralUnit
from smart_home_agent.services.cart.not_in_cart_error import NotInCartError
from smart_home_agent.services.product_not_found_error import ProductNotFoundError


class CartService:
    """Every method takes the current cart items and returns new ones (the caller stores them in the session)."""

    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog

    # Reading

    def view(self, items: Sequence[CartItem]) -> CartView:
        products = {p.id: p for p in self._catalog.get_products([item.product_id for item in items])}
        lines = []
        for item in items:
            product = products.get(item.product_id)
            price = product.price if product else None
            lines.append(
                CartLine(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    product=product,
                    unit_price=price,
                    line_total=round(price * item.quantity, 2) if price is not None else None,
                )
            )
        return CartView(
            lines=lines,
            item_count=sum(line.quantity for line in lines),
            total=round(sum(line.line_total for line in lines if line.line_total is not None), 2),
            has_unpriced=any(line.available and line.unit_price is None for line in lines),
        )

    # One add/remove tool call: changes -> (central_units_over_one) -> describe -> apply

    @staticmethod
    def changes(
        action: CartAction, product_ids: Sequence[Any], quantities: Sequence[Any] | None = None
    ) -> list[CartChange]:
        """The products of one add/remove call. `quantities` follows `product_ids` by position (default: 1 unit
        to add, all units to remove; 0 also means all units for remove). Repeated products are merged."""
        return parse_changes(action, product_ids, quantities)

    def central_units_over_one(
        self, items: Sequence[CartItem], changes: Sequence[CartChange]
    ) -> list[tuple[ProductSummary, int]]:
        """Central units (`CentralUnit.matches`) that an add of `changes` would leave in the cart more than once,
        with the units the cart would then hold. Reads the catalog only when some product would exceed one unit."""
        in_cart = {item.product_id: item.quantity for item in items}
        after = {c.product_id: in_cart.get(c.product_id, 0) + (c.quantity or 0) for c in changes}
        several = [pid for pid, units in after.items() if units > 1]
        if not several:
            return []
        return [(p, after[p.id]) for p in self._catalog.get_products(several) if CentralUnit.matches(p)]

    def describe(
        self, request_id: str, action: CartAction, args: Mapping[str, Any], items: Sequence[CartItem]
    ) -> CartConfirmation:
        """A pending change for the confirmation card, with every product read from the catalog. Arguments the
        tool will reject are still shown as they are (the tool reports the error after the decision)."""
        product_ids = args.get("product_ids") or []
        quantities = args.get("quantities")
        try:
            changes = self.changes(action, product_ids, quantities)
        except (ValueError, TypeError):
            changes = [CartChange(product_id=str(pid), quantity=None) for pid in dict.fromkeys(product_ids)]
        products = {p.id: p for p in self._catalog.get_products([c.product_id for c in changes])}
        in_cart = {item.product_id: item.quantity for item in items}
        return CartConfirmation(
            request_id=request_id,
            action=action,
            lines=[
                CartChangeLine(
                    product_id=c.product_id,
                    quantity=c.quantity,
                    product=products.get(c.product_id),
                    in_cart=in_cart.get(c.product_id, 0),
                )
                for c in changes
            ],
        )

    def apply(self, items: Sequence[CartItem], action: CartAction, changes: Sequence[CartChange]) -> list[CartItem]:
        """Applies every change, or none: raises CartChangeError listing each product that cannot be applied."""
        errors: list[dict[str, str]] = []
        if action == "add":
            known = {p.id for p in self._catalog.get_products([c.product_id for c in changes])}
            errors = [
                {"product_id": c.product_id, "status": "not_found", "message": "not in the catalog"}
                for c in changes
                if c.product_id not in known
            ]
        else:
            in_cart = {item.product_id for item in items}
            errors = [
                {"product_id": c.product_id, "status": "invalid_input", "message": "not in the cart"}
                for c in changes
                if c.product_id not in in_cart
            ]
        if errors:
            raise CartChangeError(errors)
        updated = list(items)
        for change in changes:
            if action == "add":
                updated = self._merge(updated, change.product_id, change.quantity or 1)
            else:
                updated = self.remove(updated, change.product_id, change.quantity)
        return updated

    # Single-line edits

    def add(self, items: Sequence[CartItem], product_id: str, quantity: int = 1) -> list[CartItem]:
        """Adds units (merged into an existing line, capped at MAX_QUANTITY). Only active catalog products."""
        added = parse_quantity(quantity, 1) or 1
        product_id = product_id.strip()
        if self._catalog.get_product(product_id) is None:
            raise ProductNotFoundError([product_id])
        return self._merge(items, product_id, added)

    def remove(self, items: Sequence[CartItem], product_id: str, quantity: int | None = None) -> list[CartItem]:
        """Removes `quantity` units, or the whole line when it is None or covers every unit."""
        removed = parse_quantity(quantity, None)
        product_id = product_id.strip()
        if not any(item.product_id == product_id for item in items):
            raise NotInCartError(product_id)
        current = next(item.quantity for item in items if item.product_id == product_id)
        return self.set_quantity(items, product_id, 0 if removed is None else max(current - removed, 0))

    @staticmethod
    def set_quantity(items: Sequence[CartItem], product_id: str, quantity: int) -> list[CartItem]:
        """Sets the exact quantity of a line already in the cart (the interface's stepper); 0 removes it."""
        if quantity < 0 or quantity > MAX_QUANTITY:
            raise ValueError(f"quantity must be between 0 and {MAX_QUANTITY}.")
        if not any(item.product_id == product_id for item in items):
            raise NotInCartError(product_id)
        return [
            item if item.product_id != product_id else CartItem(product_id=product_id, quantity=quantity)
            for item in items
            if item.product_id != product_id or quantity > 0
        ]

    @staticmethod
    def _merge(items: Sequence[CartItem], product_id: str, quantity: int) -> list[CartItem]:
        updated = [item.model_copy() for item in items]
        for item in updated:
            if item.product_id == product_id:
                item.quantity = min(item.quantity + quantity, MAX_QUANTITY)
                return updated
        return [*updated, CartItem(product_id=product_id, quantity=quantity)]
