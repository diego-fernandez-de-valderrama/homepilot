import html

from smart_home_agent.models import Product
from smart_home_agent.ui.components._markup import Markup


class ProductCardHtml:
    """The product cards of an <items> block, from catalog data only."""

    @staticmethod
    def cards(products: list[Product], missing_images: frozenset[str] = frozenset()) -> str:
        """`missing_images`: image URLs known to be gone; those cards leave the image out
        (text-only layout) instead of showing a blank box."""
        return f'<div class="hp-cards">{"".join(ProductCardHtml._card(p, missing_images) for p in products)}</div>'

    @staticmethod
    def image_urls(products: list[Product]) -> tuple[str, ...]:
        """The image URLs the product components would load (the ones worth checking for availability)."""
        return tuple(dict.fromkeys(url for p in products if (url := Markup.safe_url(p.image_url))))

    @staticmethod
    def _card(product: Product, missing_images: frozenset[str]) -> str:
        image = Markup.image(product, missing_images, "hp-card__image")
        brand = f'<span class="hp-card__brand">{html.escape(product.brand)}</span>' if product.brand else ""
        was = (
            f'<s class="hp-card__was">{html.escape(Markup.price(product.original_price))}</s>'
            if product.original_price and product.price is not None and product.original_price > product.price
            else ""
        )
        source_url = Markup.safe_url(product.source_url)
        link = (
            f'<a class="hp-card__link" href="{html.escape(source_url)}" target="_blank" rel="noopener">View in shop</a>'
            if source_url
            else ""
        )
        card_class = "hp-card" if image else "hp-card hp-card--no-image"
        return (
            f'<article class="{card_class}">'
            f"{image}{brand}"
            f'<span class="hp-card__title">{html.escape(product.title)}</span>{Markup.version(product, "hp-card")}'
            f'<span class="hp-card__price">{html.escape(Markup.price(product.price))}{was}</span>'
            f"{link}</article>"
        )
