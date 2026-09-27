from collections.abc import Sequence

from smart_home_agent.models import AccessorySuggestion, Product, ProductFilter, RequirementCheck
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services.accessories._hub_titles import HUB_CATEGORY, HUB_TITLE_KEYWORDS, is_bare_hub


class AccessoryService:
    """Only the ids of the matching hub products are cached (per requirement, for the process lifetime); price
    and availability are read from PostgreSQL on every call, so a re-ingest never shows a stale price or an
    inactive hub."""

    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog
        self._hub_ids: dict[str, list[str]] = {}  # canonical requirement id -> bare hub product ids

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

    def hub_for(self, canonical_item: str) -> Product | None:
        """Cheapest bare hub product for a canonical requirement id, or None without a safe mapping."""
        keywords = HUB_TITLE_KEYWORDS.get(canonical_item)
        if not keywords:
            return None
        ids = self._candidate_ids(canonical_item, keywords)
        current = [p for p in self._catalog.get_products(ids) if p.price is not None] if ids else []
        return min(current, key=lambda p: (p.price or 0.0, p.id)) if current else None

    def _candidate_ids(self, canonical_item: str, keywords: Sequence[str]) -> list[str]:
        if canonical_item not in self._hub_ids:
            _, products = self._catalog.filter_products(ProductFilter(category=HUB_CATEGORY, limit=500))
            self._hub_ids[canonical_item] = [p.id for p in products if is_bare_hub(p, keywords)]
        return self._hub_ids[canonical_item]
