from smart_home_agent.models import Product
from smart_home_agent.ui.components._templates import Templates


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
        return Templates.render(
            "item_chip",
            "render",
            product=product,
            product_id=product_id,
            shown_in_block=shown_in_block,
            missing_images=missing_images,
        )
