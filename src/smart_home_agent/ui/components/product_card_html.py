from smart_home_agent.models import Product
from smart_home_agent.ui.components._markup import Markup
from smart_home_agent.ui.components._templates import Templates


class ProductCardHtml:
    """The product cards of an <items> block, from catalog data only."""

    @staticmethod
    def cards(products: list[Product], missing_images: frozenset[str] = frozenset()) -> str:
        """`missing_images`: image URLs known to be gone; those cards leave the image out
        (text-only layout) instead of showing a blank box."""
        return Templates.render("product_card", "cards", products=products, missing_images=missing_images)

    @staticmethod
    def image_urls(products: list[Product]) -> tuple[str, ...]:
        """The image URLs the product components would load (the ones worth checking for availability)."""
        return tuple(dict.fromkeys(url for p in products if (url := Markup.safe_url(p.image_url))))
