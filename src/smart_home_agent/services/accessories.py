"""Hub/gateway cross-sell: the catalog product that satisfies a required hub the customer may not own yet.

A product whose hub requirement is `missing` (the customer said they do not own it) or `unverified` (ownership
not stated) is only usable with that hub, so offering the hub is a factual, data-backed basket addition.
The mapping is keyed by the canonical requirement ids of `catalog_ingestion/vocabulary/requirements.py` and
matches plain hub products in the `hub_gateway` category by title keywords (starter sets are never offered).
Requirements without a safe mapping (generic `smart_hub`, partner solutions) get no suggestion.
"""

from collections.abc import Sequence

from smart_home_agent.models.compatibility import AccessorySuggestion, RequirementCheck
from smart_home_agent.models.product import Product
from smart_home_agent.models.search import ProductFilter
from smart_home_agent.repositories.postgres import CatalogReader

HUB_CATEGORY = "hub_gateway"

# canonical requirement id -> keywords that must all appear in the hub product's title (case-insensitive)
HUB_TITLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "homematic_ip_access_point": ("homematic", "access point"),
    "homematic_ccu3": ("homematic", "ccu3"),
    "bosch_smart_home_controller": ("bosch", "smart home controller"),
    "philips_hue_bridge": ("hue", "bridge"),
    "gardena_smart_gateway": ("gardena", "gateway"),
    "ring_alarm_base_station": ("ring", "basisstation"),
}
_BUNDLE_WORDS = ("set",)  # "Starter-Set", "Set": bundles with other devices are not the bare hub


def _is_bare_hub(product: Product, keywords: Sequence[str]) -> bool:
    title = product.title.casefold()
    words = set(title.replace("-", " ").split())
    return all(k in title for k in keywords) and not words & set(_BUNDLE_WORDS)


class AccessoryService:
    """Only the ids of the matching hub products are cached (per requirement, for the process lifetime); price
    and availability are read from PostgreSQL on every call, so a re-ingest never shows a stale price or an
    inactive hub."""

    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog
        self._hub_ids: dict[str, list[str]] = {}  # canonical requirement id -> bare hub product ids

    def _candidate_ids(self, canonical_item: str, keywords: Sequence[str]) -> list[str]:
        if canonical_item not in self._hub_ids:
            _, products = self._catalog.filter_products(ProductFilter(category=HUB_CATEGORY, limit=500))
            self._hub_ids[canonical_item] = [p.id for p in products if _is_bare_hub(p, keywords)]
        return self._hub_ids[canonical_item]

    def hub_for(self, canonical_item: str) -> Product | None:
        """Cheapest bare hub product for a canonical requirement id, or None without a safe mapping."""
        keywords = HUB_TITLE_KEYWORDS.get(canonical_item)
        if not keywords:
            return None
        ids = self._candidate_ids(canonical_item, keywords)
        current = [p for p in self._catalog.get_products(ids) if p.price is not None] if ids else []
        return min(current, key=lambda p: (p.price or 0.0, p.id)) if current else None

    def for_product(self, product: Product, requirements: Sequence[RequirementCheck]) -> list[AccessorySuggestion]:
        """Hub suggestions for the required hubs of `product` that are `missing` or `unverified`."""
        suggestions: list[AccessorySuggestion] = []
        for check in requirements:
            if check.status not in ("missing", "unverified") or not check.canonical_item:
                continue
            hub = self.hub_for(check.canonical_item)
            if hub is None or hub.price is None or product.price is None or hub.id == product.id:
                continue
            suggestions.append(
                AccessorySuggestion(
                    for_product_id=product.id,
                    requirement_label=check.label,
                    canonical_item=check.canonical_item,
                    status=check.status,
                    product_id=hub.id,
                    title=hub.title,
                    price=hub.price,
                    bundle_total=round(product.price + hub.price, 2),
                )
            )
        return suggestions
