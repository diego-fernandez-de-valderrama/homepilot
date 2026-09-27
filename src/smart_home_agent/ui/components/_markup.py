import html
import re
from collections.abc import Callable

from smart_home_agent.models import Product, ProductSummary

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#+!|$~])")


class Markup:
    """Small escaping and formatting pieces shared by the HTML components."""

    @staticmethod
    def price(value: float | None) -> str:
        return f"{value:,.2f} €" if value is not None else "price not listed"

    @staticmethod
    def safe_url(url: str | None) -> str | None:
        return url if url and url.startswith(("https://", "http://")) else None

    @staticmethod
    def markdown_literal(value: str) -> str:
        """Text placed between HTML tags inside markdown is still parsed as markdown: neutralize its syntax."""
        # quote=False: only text nodes use this, and "&#x27;" would get its "#" escaped and show up literally.
        return _MARKDOWN_SPECIAL.sub(r"\\\1", html.escape(value, quote=False))

    @staticmethod
    def chips(values: list[str]) -> str:
        return "".join(f'<span class="hp-chip">{html.escape(v)}</span>' for v in values)

    @staticmethod
    def image(product: Product, missing_images: frozenset[str], css_class: str) -> str:
        """The product image, or "" when there is none (or it is known to be gone): the card then uses its
        text-only layout instead of showing a placeholder."""
        image_url = Markup.safe_url(product.image_url)
        if image_url and image_url not in missing_images:
            return f'<img class="{css_class}" src="{html.escape(image_url)}" alt="" loading="lazy">'
        return ""

    @staticmethod
    def thumb(product: Product | None, missing_images: frozenset[str], css_class: str) -> str:
        """Cart and confirmation thumbnails: the product image, or a quiet package glyph when there is none
        (a missing image is not information for the customer, so no "No image" text)."""
        image_url = Markup.safe_url(product.image_url) if product else None
        if image_url and image_url not in missing_images:
            return f'<img class="{css_class}" src="{html.escape(image_url)}" alt="" loading="lazy">'
        return (
            f'<span class="{css_class} {css_class}--empty" aria-hidden="true">'
            '<span class="hp-thumb-glyph">inventory_2</span></span>'
        )

    @staticmethod
    def version(product: ProductSummary, block: str, escape: Callable[[str], str] = html.escape) -> str:
        """The line that tells versions of one product apart (the catalog subtitle, e.g. "GU10, RGBW, Weiß").
        `escape`: `markdown_literal` inside markdown (the item chip), plain HTML escaping elsewhere."""
        if not product.subtitle:
            return ""
        return f'<span class="{block}__version">{escape(product.subtitle)}</span>'
