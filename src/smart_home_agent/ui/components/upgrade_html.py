import html

from smart_home_agent.models import Product, UpsellSuggestion
from smart_home_agent.ui.components._markup import Markup


class UpgradeHtml:
    """The <upgrade> block: the best match, the upsell, the price difference and the data-based reasons."""

    @staticmethod
    def render(base: Product, target: Product, upsell: UpsellSuggestion) -> str:
        reasons = "".join(f"<li>{html.escape(r)}</li>" for r in upsell.upgrade_reasons)
        return (
            '<section class="hp-upgrade">'
            '<p class="hp-eyebrow">Upgrade option</p>'
            '<div class="hp-upgrade__pair">'
            f"{UpgradeHtml._product('Your match', base)}"
            '<span class="hp-upgrade__arrow" aria-hidden="true">→</span>'
            f"{UpgradeHtml._product('Upgrade', target)}"
            "</div>"
            f'<p class="hp-upgrade__delta">+{html.escape(Markup.price(upsell.price_difference))}</p>'
            + (f'<ul class="hp-upgrade__reasons">{reasons}</ul>' if reasons else "")
            + "</section>"
        )

    @staticmethod
    def _product(label: str, product: Product) -> str:
        return (
            f'<div class="hp-upgrade__product"><span class="hp-upgrade__label">{label}</span>'
            f"<span>{html.escape(product.title)}</span>{Markup.version(product, 'hp-upgrade')}"
            f"<span>{html.escape(Markup.price(product.price))}</span></div>"
        )
