from smart_home_agent.models import EvidenceResult
from smart_home_agent.repositories import CatalogReader
from smart_home_agent.services.evidence.evidence_lookup import EvidenceLookup
from smart_home_agent.services.product_not_found_error import ProductNotFoundError


class EvidenceService:
    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog

    def get(self, product_id: str, topic: str) -> EvidenceResult:
        products = self._catalog.get_products([product_id])
        if not products:
            raise ProductNotFoundError([product_id])
        return EvidenceLookup.for_product(products[0], topic)
