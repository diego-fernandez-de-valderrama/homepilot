import html

from smart_home_agent.models import CartLine, CartView
from smart_home_agent.ui.components._markup import Markup


class CartHtml:
    """The cart in the customer panel (its stepper buttons are Streamlit widgets rendered below each line)."""

    @staticmethod
    def header(view: CartView) -> str:
        count = f'<span class="hp-cart__count">{view.item_count}</span>' if view.item_count else ""
        empty = (
            '<p class="hp-cart__empty">Your cart is empty. Ask HomePilot to add a product.</p>'
            if not view.lines
            else ""
        )
        return f'<div class="hp-cart"><p class="hp-panel-label hp-cart__label">Your cart{count}</p>{empty}</div>'

    @staticmethod
    def line(line: CartLine, missing_images: frozenset[str] = frozenset()) -> str:
        product = line.product
        if product is None:
            return (
                '<div class="hp-cart__line hp-cart__line--gone">'
                f"{Markup.thumb(None, missing_images, 'hp-cart__thumb')}"
                f'<div class="hp-cart__info"><span class="hp-cart__title">Product {html.escape(line.product_id)}</span>'
                '<span class="hp-cart__note">No longer available</span></div></div>'
            )
        brand = f'<span class="hp-cart__brand">{html.escape(product.brand)}</span>' if product.brand else ""
        subtotal = (
            f'<span class="hp-cart__subtotal">{line.quantity} × {html.escape(Markup.price(line.unit_price))}</span>'
            if line.quantity > 1 and line.unit_price is not None
            else ""
        )
        return (
            '<div class="hp-cart__line">'
            f"{Markup.thumb(product, missing_images, 'hp-cart__thumb')}"
            f'<div class="hp-cart__info">{brand}<span class="hp-cart__title">{html.escape(product.title)}</span>'
            f"{Markup.version(product, 'hp-cart')}"
            f'<span class="hp-cart__price">{html.escape(Markup.price(line.line_total))}</span>{subtotal}</div></div>'
        )

    @staticmethod
    def total(view: CartView) -> str:
        note = '<p class="hp-cart__note">Some prices are not listed and not included.</p>' if view.has_unpriced else ""
        return (
            '<div class="hp-cart__total"><span>Total</span>'
            f'<span class="hp-cart__total-value">{html.escape(Markup.price(view.total))}</span></div>{note}'
        )
