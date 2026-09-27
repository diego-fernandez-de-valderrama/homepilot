"""Resolves the presentation tags of an answer to catalog data (PostgreSQL only).

A tag whose data cannot be resolved (unknown id, a comparison of fewer than two known products, an
upgrade that is not the recommender's upsell) gets no entry, and the UI then drops or degrades it.
"""

from collections.abc import Sequence

from smart_home_agent.answer_tags import CompareBlock, CompatibilityBlock, TagParser, UpgradeBlock
from smart_home_agent.models import CAPABILITY_DIMENSIONS, Product, ProductCompatibility, RichContent, UpsellSuggestion
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services import vocabulary
from smart_home_agent.services.comparison import MAX_PRODUCTS, MIN_PRODUCTS, compare
from smart_home_agent.services.compatibility import evaluate
from smart_home_agent.services.vocabulary import ResolvedTerm, TermResolutionError


def _terms(canonicals: Sequence[str]) -> list[ResolvedTerm]:
    terms = []
    for canonical in dict.fromkeys(canonicals):
        try:
            terms.append(vocabulary.term(canonical))
        except TermResolutionError:
            continue
    return terms


def _own_terms(product: Product) -> list[ResolvedTerm]:
    return _terms(
        [f.canonical_value for f in product.compatibility if f.canonical_value and f.dimension in CAPABILITY_DIMENSIONS]
    )


def product_compatibility(
    product: Product, must_support: Sequence[str], owned_devices: Sequence[str] | None
) -> ProductCompatibility:
    """Against the customer's setup when it is known, otherwise the product's own capability facts.
    Statuses come from `evaluate` unchanged: unknown stays unknown."""
    setup = _terms(must_support)
    terms = setup or _own_terms(product)
    return ProductCompatibility(result=evaluate(product, terms, owned_devices), against_setup=bool(setup))


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
                    content.compatibility[product_id] = product_compatibility(
                        products[product_id], must_support, owned_devices
                    )
                case CompareBlock(block_ids):
                    known = [products[pid] for pid in block_ids if pid in products]
                    if MIN_PRODUCTS <= len(known) <= MAX_PRODUCTS:
                        content.comparisons[RichContent.compare_key(block_ids)] = compare(known)
                case UpgradeBlock(from_id, to_id):
                    if (
                        last_upsell is not None
                        and (last_upsell.base_product_id, last_upsell.product_id) == (from_id, to_id)
                        and {from_id, to_id} <= products.keys()
                    ):
                        content.upgrades[RichContent.upgrade_key(from_id, to_id)] = last_upsell
        return content
