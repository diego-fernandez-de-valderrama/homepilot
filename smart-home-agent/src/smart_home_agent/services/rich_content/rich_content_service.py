from collections.abc import Sequence

from smart_home_agent.answer_tags import CompareBlock, CompatibilityBlock, TagParser, UpgradeBlock
from smart_home_agent.models import Product, ProductCompatibility, RichContent, UpsellSuggestion
from smart_home_agent.repositories import CatalogReader
from smart_home_agent.services.comparison import ProductComparer
from smart_home_agent.services.compatibility import CompatibilityEvaluator
from smart_home_agent.services.rich_content._setup_terms import known_terms, own_terms


class RichContentService:
    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog

    def resolve(
        self,
        text: str,
        must_support: Sequence[str] = (),
        owned_devices: Sequence[str] | None = None,
        last_upsell: UpsellSuggestion | None = None,
    ) -> RichContent | None:
        """`must_support`/`owned_devices`: the customer's canonical setup from the session; `last_upsell`: the
        recommender's latest upsell, the only pair an <upgrade/> may show. None when there is no tag."""
        segments = TagParser.parse(text)
        ids = TagParser.referenced_ids(segments)
        if not ids:
            return None
        products = {p.id: p for p in self._catalog.get_products(ids)}
        content = RichContent(products=products)
        for segment in segments:
            match segment:
                case CompatibilityBlock(product_id) if product_id in products:
                    content.compatibility[product_id] = self.product_compatibility(
                        products[product_id], must_support, owned_devices
                    )
                case CompareBlock(block_ids):
                    known = [products[pid] for pid in block_ids if pid in products]
                    if ProductComparer.MIN_PRODUCTS <= len(known) <= ProductComparer.MAX_PRODUCTS:
                        content.comparisons[RichContent.compare_key(block_ids)] = ProductComparer.compare(known)
                case UpgradeBlock(from_id, to_id):
                    if (
                        last_upsell is not None
                        and (last_upsell.base_product_id, last_upsell.product_id) == (from_id, to_id)
                        and {from_id, to_id} <= products.keys()
                    ):
                        content.upgrades[RichContent.upgrade_key(from_id, to_id)] = last_upsell
        return content

    @staticmethod
    def product_compatibility(
        product: Product, must_support: Sequence[str], owned_devices: Sequence[str] | None
    ) -> ProductCompatibility:
        """Against the customer's setup when it is known, otherwise the product's own capability facts.
        Statuses come from `CompatibilityEvaluator.evaluate` unchanged: unknown stays unknown."""
        setup = known_terms(must_support)
        terms = setup or own_terms(product)
        return ProductCompatibility(
            result=CompatibilityEvaluator.evaluate(product, terms, owned_devices), against_setup=bool(setup)
        )
