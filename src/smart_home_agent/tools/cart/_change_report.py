from typing import Any

from smart_home_agent.models import CartAction, CartView
from smart_home_agent.repositories import CatalogReader
from smart_home_agent.tools._base import ToolResult


class ChangeReport:
    """The result shape of every add or remove, also when it failed, waits for confirmation or was cancelled."""

    @staticmethod
    def build(
        status: str,
        action: CartAction,
        product_ids: list[str],
        before: CartView,
        after: CartView,
        message: str | None = None,
        errors: list[dict[str, str]] | None = None,
        catalog: CatalogReader | None = None,
    ) -> ToolResult:
        """Outcome of an add or remove: success or failure, per product the units changed and the units left
        (or a note that none are left), and the remaining cart lines (or a note that the cart is empty).
        `catalog` names the products that are in neither cart view (an add waiting for confirmation)."""
        products = {line.product_id: line.product for line in after.lines + before.lines if line.product}
        missing = [pid for pid in product_ids if pid not in products]
        if catalog is not None and missing:
            products.update({p.id: p for p in catalog.get_products(missing)})
        changes = []
        for pid in product_ids:
            remaining = after.quantity_of(pid)
            product = products.get(pid)
            change: dict[str, Any] = {
                "product_id": pid,
                "title": product.title if product else None,
                "variant": product.variant if product else None,
                "subtitle": product.subtitle if product else None,
                "quantity_changed": abs(remaining - before.quantity_of(pid)),
                "remaining_of_product": remaining,
            }
            if remaining == 0:
                change["note"] = "none of this product left in the cart"
            changes.append(change)
        result: ToolResult = {
            "status": status,
            "action": action,
            "changes": changes,
            "remaining_items": after.for_model(),
            "cart_total": after.total,
        }
        if not after.lines:
            result["note"] = "the cart is empty"
        if message:
            result["message"] = message
        if errors:
            result["errors"] = errors
        return result
