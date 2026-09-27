"""Shopping cart operations over the session's cart items. Pure list updates plus one catalog read per view:
prices and titles always come from PostgreSQL, never from the session.

One add/remove call can cover several products. It is applied all or nothing: the customer confirmed the
whole change, so a change with any invalid product leaves the cart untouched and reports every problem."""

from collections.abc import Mapping, Sequence
from typing import Any

from smart_home_agent.models.cart import (
    MAX_QUANTITY,
    CartAction,
    CartChange,
    CartChangeLine,
    CartConfirmation,
    CartItem,
    CartLine,
    CartView,
)
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services.compatibility import ProductNotFoundError


class NotInCartError(ValueError):
    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product {product_id} is not in the cart.")
        self.product_id = product_id


MAX_PRODUCTS_PER_CHANGE = 20


class CartChangeError(ValueError):
    """Products of a change that cannot be applied; `errors` has one entry per product with its reason."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{e['product_id']}: {e['message']}" for e in errors))
        self.errors = errors

    @property
    def status(self) -> str:
        return "not_found" if all(e["status"] == "not_found" for e in self.errors) else "invalid_input"


def _quantity(value: Any, default: int | None) -> int | None:
    if value is None:
        return default
    quantity = int(value)
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError(f"quantity must be between 1 and {MAX_QUANTITY}.")
    return quantity


class CartService:
    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog

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

    def add(self, items: Sequence[CartItem], product_id: str, quantity: int = 1) -> list[CartItem]:
        """Adds units (merged into an existing line, capped at MAX_QUANTITY). Only active catalog products."""
        added = _quantity(quantity, 1) or 1
        product_id = product_id.strip()
        if self._catalog.get_product(product_id) is None:
            raise ProductNotFoundError([product_id])
        return self._merge(items, product_id, added)

    def remove(self, items: Sequence[CartItem], product_id: str, quantity: int | None = None) -> list[CartItem]:
        """Removes `quantity` units, or the whole line when it is None or covers every unit."""
        removed = _quantity(quantity, None)
        product_id = product_id.strip()
        if not any(item.product_id == product_id for item in items):
            raise NotInCartError(product_id)
        current = next(item.quantity for item in items if item.product_id == product_id)
        return self.set_quantity(items, product_id, 0 if removed is None else max(current - removed, 0))

    def set_quantity(self, items: Sequence[CartItem], product_id: str, quantity: int) -> list[CartItem]:
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

    def changes(
        self, action: CartAction, product_ids: Sequence[Any], quantities: Sequence[Any] | None = None
    ) -> list[CartChange]:
        """The products of one add/remove call. `quantities` follows `product_ids` by position (default: 1 unit
        to add, all units to remove; 0 also means all units for remove). Repeated products are merged."""
        ids = [str(pid).strip() for pid in product_ids]
        if not ids or any(not pid for pid in ids):
            raise ValueError("product_ids must list at least one product id.")
        if len(dict.fromkeys(ids)) > MAX_PRODUCTS_PER_CHANGE:
            raise ValueError(f"at most {MAX_PRODUCTS_PER_CHANGE} products per change.")
        if quantities is not None and len(quantities) != len(ids):
            raise ValueError("quantities must have one entry per product id, in the same order.")
        raw = list(quantities) if quantities is not None else [None] * len(ids)
        merged: dict[str, int | None] = {}
        for pid, value in zip(ids, raw, strict=True):
            if action == "add":
                units = _quantity(value, 1) or 1
                merged[pid] = min((merged.get(pid) or 0) + units, MAX_QUANTITY)
            else:
                units = None if value is None or int(value) == 0 else _quantity(value, None)
                if units is None or (pid in merged and merged[pid] is None):
                    merged[pid] = None  # "all units" wins over any partial amount of the same product
                else:
                    total = (merged.get(pid) or 0) + units
                    # A line holds at most MAX_QUANTITY units: removing that many (or more) removes all of them.
                    merged[pid] = None if total >= MAX_QUANTITY else total
        return [CartChange(product_id=pid, quantity=quantity) for pid, quantity in merged.items()]

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

    @staticmethod
    def _merge(items: Sequence[CartItem], product_id: str, quantity: int) -> list[CartItem]:
        updated = [item.model_copy() for item in items]
        for item in updated:
            if item.product_id == product_id:
                item.quantity = min(item.quantity + quantity, MAX_QUANTITY)
                return updated
        return [*updated, CartItem(product_id=product_id, quantity=quantity)]

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
