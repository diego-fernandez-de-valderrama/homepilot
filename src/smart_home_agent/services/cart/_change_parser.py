from collections.abc import Sequence
from typing import Any

from smart_home_agent.models import MAX_QUANTITY, CartAction, CartChange
from smart_home_agent.services.cart._quantity import parse_quantity

MAX_PRODUCTS_PER_CHANGE = 20


def parse_changes(
    action: CartAction, product_ids: Sequence[Any], quantities: Sequence[Any] | None = None
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
            units = parse_quantity(value, 1) or 1
            merged[pid] = min((merged.get(pid) or 0) + units, MAX_QUANTITY)
        else:
            units = None if value is None or int(value) == 0 else parse_quantity(value, None)
            if units is None or (pid in merged and merged[pid] is None):
                merged[pid] = None  # "all units" wins over any partial amount of the same product
            else:
                total = (merged.get(pid) or 0) + units
                # A line holds at most MAX_QUANTITY units: removing that many (or more) removes all of them.
                merged[pid] = None if total >= MAX_QUANTITY else total
    return [CartChange(product_id=pid, quantity=quantity) for pid, quantity in merged.items()]
