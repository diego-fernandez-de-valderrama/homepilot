import html

from smart_home_agent.models import CartChangeLine, CartConfirmation
from smart_home_agent.ui.components._markup import Markup
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
        lines = "".join(ConfirmationHtml._line(confirmation, line, missing_images) for line in confirmation.lines)
        total = ""
        if count > 1 and confirmation.total is not None:
            change = ("+" if adding else "−") + html.escape(Markup.price(confirmation.total))
            total = (
                '<p class="hp-confirm__total"><span>Change total</span>'
                f'<span class="hp-confirm__total-value">{change}</span></p>'
            )
        modifier = "add" if adding else "remove"
        return (
            f'<section class="hp-confirm hp-confirm--{modifier}{" hp-confirm--done" if state else ""}">'
            f'<p class="hp-eyebrow">{eyebrow}</p><ul class="hp-confirm__lines">{lines}</ul>{total}'
            f"{ConfirmationHtml._status(confirmation, state)}</section>"
        )

    @staticmethod
    def lead(count: int) -> str:
        text = (
            "Please confirm this change to your cart." if count == 1 else "Please confirm these changes to your cart."
        )
        return f'<p class="hp-confirm-lead">{text}</p>'

    @staticmethod
    def button_label(confirmation: CartConfirmation) -> str:
        count = len(confirmation.lines)
        if confirmation.action == "add":
            return "Add to cart" if count == 1 else f"Add {count} products"
        return "Remove" if count == 1 else f"Remove {count} products"

    @staticmethod
    def _status(confirmation: CartConfirmation, state: ConfirmationState) -> str:
        if state is None:
            return ""
        if state == "expired":
            return '<span class="hp-confirm__state hp-confirm__state--expired">Not confirmed</span>'
        text = CONFIRM_STATE_TEXT[(confirmation.action, state)]
        return f'<span class="hp-confirm__state hp-confirm__state--{state}">{html.escape(text)}</span>'

    @staticmethod
    def _line(confirmation: CartConfirmation, line: CartChangeLine, missing_images: frozenset[str]) -> str:
        product = line.product
        amount = (
            str(line.quantity) if line.quantity is not None else (f"All {line.in_cart}" if line.in_cart > 1 else "1")
        )
        price = product.price if product else None
        detail = f"{amount} × {Markup.price(price)}"
        if price is not None and line.units > 1:
            detail += f" = {Markup.price(round(price * line.units, 2))}"
        in_cart = f"In your cart now: {line.in_cart} · after this change: {confirmation.after(line)}"
        title = product.title if product else f"Product {line.product_id} (not in the catalog)"
        return (
            f'<li class="hp-confirm__body">{Markup.thumb(product, missing_images, "hp-confirm__image")}'
            f'<div class="hp-confirm__info"><span class="hp-confirm__title">{html.escape(title)}</span>'
            f"{Markup.version(product, 'hp-confirm') if product else ''}"
            f'<span class="hp-confirm__detail">{html.escape(detail)}</span>'
            f'<span class="hp-confirm__cart">{html.escape(in_cart)}</span></div></li>'
        )
