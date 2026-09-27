from smart_home_agent.models import Product, UpsellSuggestion
from smart_home_agent.ui.components._templates import Templates


class UpgradeHtml:
    """The <upgrade> block: the best match, the upsell, the price difference and the data-based reasons."""

    @staticmethod
    def render(base: Product, target: Product, upsell: UpsellSuggestion) -> str:
        return Templates.render("upgrade", "render", base=base, target=target, upsell=upsell)
