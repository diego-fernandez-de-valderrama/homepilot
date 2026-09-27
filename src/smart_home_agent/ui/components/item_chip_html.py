import html

from smart_home_agent.models import Product
from smart_home_agent.ui.components._markup import Markup


class ItemChipHtml:
    """Inline <item/>: a chip with the catalog name that reveals a mini product card on hover or focus."""

    @staticmethod
    def render(
        product: Product | None,
        product_id: str,
        shown_in_block: bool = False,
        missing_images: frozenset[str] = frozenset(),
    ) -> str:
        """The chip shows the price unless a block of the same answer already shows the product. One line of
        inline HTML inside markdown, so only <span>, <img> and <a> are used. The bare id when the product is
        unknown."""
        if product is None:
            return Markup.markdown_literal(product_id)
        price = Markup.price(product.price)
        price_html = "" if shown_in_block else f'<span class="hp-item__price">{Markup.markdown_literal(price)}</span>'
        return (
            f'<span class="hp-item" tabindex="0">'
            f'<span class="hp-item__name">{Markup.markdown_literal(product.title)}</span>'
            f"{price_html}{ItemChipHtml._card(product, price, missing_images)}</span>"
        )

    @staticmethod
    def _card(product: Product, price: str, missing_images: frozenset[str]) -> str:
        brand = f'<span class="hp-item__brand">{Markup.markdown_literal(product.brand)}</span>' if product.brand else ""
        source_url = Markup.safe_url(product.source_url)
        link = (
            f'<a class="hp-item__link" href="{html.escape(source_url)}" target="_blank" rel="noopener">View in shop</a>'
            if source_url
            else ""
        )
        version = Markup.version(product, "hp-item", Markup.markdown_literal)
        image = Markup.image(product, missing_images, "hp-item__image")
        card_class = "hp-item__card" if image else "hp-item__card hp-item__card--no-image"
        return (
            f'<span class="{card_class}" role="tooltip">'
            f"{image}{brand}"
            f'<span class="hp-item__title">{Markup.markdown_literal(product.title)}</span>{version}'
            f'<span class="hp-item__card-price">{Markup.markdown_literal(price)}</span>{link}</span>'
        )
