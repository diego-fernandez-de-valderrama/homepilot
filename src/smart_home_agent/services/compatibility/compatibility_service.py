from collections.abc import Sequence

from smart_home_agent.models import CompatibilityResult
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services.accessories import AccessoryService
from smart_home_agent.services.compatibility.compatibility_evaluator import CompatibilityEvaluator
from smart_home_agent.services.product_not_found_error import ProductNotFoundError
from smart_home_agent.services.vocabulary import ResolvedTerm


class CompatibilityService:
    def __init__(self, catalog: CatalogReader, accessories: AccessoryService | None = None) -> None:
        self._catalog = catalog
        self._accessories = accessories

    def check(
        self, product_ids: Sequence[str], terms: Sequence[ResolvedTerm], owned_devices: Sequence[str] | None = None
    ) -> list[CompatibilityResult]:
        products = self._catalog.get_products(product_ids)
        missing = [pid for pid in product_ids if pid not in {p.id for p in products}]
        if missing:
            raise ProductNotFoundError(missing)
        results = []
        for product in products:
            result = CompatibilityEvaluator.evaluate(product, terms, owned_devices)
            if self._accessories:  # the catalog hub products for required hubs the customer may not own
                result.accessories = self._accessories.for_product(product, result.requirements)
            results.append(result)
        return results
