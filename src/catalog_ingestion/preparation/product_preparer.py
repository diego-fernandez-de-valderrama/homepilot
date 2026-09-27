from catalog_ingestion.core import Hashing
from catalog_ingestion.models import RawProduct
from catalog_ingestion.preparation.compatibility_extractor import CompatibilityExtractor
from catalog_ingestion.preparation.completeness_assessor import CompletenessAssessor
from catalog_ingestion.preparation.prepared_product import PreparedProduct
from catalog_ingestion.preparation.product_normalizer import ProductNormalizer
from catalog_ingestion.preparation.requirement_extractor import RequirementExtractor


class ProductPreparer:
    """The deterministic stages of one product (pure, no I/O)."""

    @staticmethod
    def prepare(raw: RawProduct) -> PreparedProduct:
        """Normalization, deterministic extraction and completeness analysis."""
        product = ProductNormalizer.normalize(raw)
        facts = CompatibilityExtractor.extract(product)
        return PreparedProduct(
            raw=raw,
            raw_hash=Hashing.sha256_json(dict(raw.original)),
            product=product,
            facts=facts,
            requirements=RequirementExtractor.extract(product),
            completeness=CompletenessAssessor.assess(product, facts),
        )
