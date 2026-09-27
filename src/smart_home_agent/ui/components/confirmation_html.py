from typing import Any

from smart_home_agent.models import CartChangeLine, CartConfirmation
from smart_home_agent.ui.components._markup import Markup
from smart_home_agent.ui.components._templates import Templates
from smart_home_agent.ui.components._texts import CONFIRM_STATE_TEXT
from smart_home_agent.ui.components.confirmation_state import ConfirmationState


class ConfirmationHtml:
    """The card of a proposed cart change (its buttons are Streamlit widgets rendered below it)."""

    @staticmethod
    def card(
        confirmation: CartConfirmation, state: ConfirmationState = None, missing_images: frozenset[str] = frozenset()
    ) -> str:
        """The change the advisor proposes (one or more products, confirmed together), from catalog data only."""
        adding = confirmation.action == "add"
        count = len(confirmation.lines)
        eyebrow = ("Add to cart" if adding else "Remove from cart") + (f" · {count} products" if count > 1 else "")
        total = None
        if count > 1 and confirmation.total is not None:
            total = ("+" if adding else "−") + Markup.price(confirmation.total)
        return Templates.render(
            "confirmation",
            "card",
            action=confirmation.action,
            done=state is not None,
            eyebrow=eyebrow,
            lines=[ConfirmationHtml._line(confirmation, line) for line in confirmation.lines],
            total=total,
            state=state,
            state_text=ConfirmationHtml._state_text(confirmation, state),
            missing_images=missing_images,
        )

    @staticmethod
    def lead(count: int) -> str:
        return Templates.render("confirmation", "lead", count=count)

    @staticmethod
    def button_label(confirmation: CartConfirmation) -> str:
        count = len(confirmation.lines)
        if confirmation.action == "add":
            return "Add to cart" if count == 1 else f"Add {count} products"
        return "Remove" if count == 1 else f"Remove {count} products"

    @staticmethod
    def _state_text(confirmation: CartConfirmation, state: ConfirmationState) -> str | None:
        if state is None:
            return None
        if state == "expired":
            return "Not confirmed"
        return CONFIRM_STATE_TEXT[(confirmation.action, state)]

    @staticmethod
    def _line(confirmation: CartConfirmation, line: CartChangeLine) -> dict[str, Any]:
        product = line.product
        amount = (
            str(line.quantity) if line.quantity is not None else (f"All {line.in_cart}" if line.in_cart > 1 else "1")
        )
        price = product.price if product else None
        detail = f"{amount} × {Markup.price(price)}"
        if price is not None and line.units > 1:
            detail += f" = {Markup.price(round(price * line.units, 2))}"
        return {
            "product": product,
            "title": product.title if product else f"Product {line.product_id} (not in the catalog)",
            "detail": detail,
            "in_cart": f"In your cart now: {line.in_cart} · after this change: {confirmation.after(line)}",
        }
