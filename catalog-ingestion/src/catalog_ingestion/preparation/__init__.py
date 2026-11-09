"""Stage 1, deterministic (pure, no I/O besides reading the zip): products.zip -> `PreparedProduct`s.
Import everything from here:

    from catalog_ingestion.preparation import ProductPreparer, ZipLoader, ...

Flow, driven per product by `ProductPreparer.prepare`:

1. `ZipLoader.load`: `info/<id>.json` -> `RawProduct`s (+ `LoadError`s for unreadable files) in a `LoadResult`.
2. `ProductNormalizer.normalize`: price, attributes blob, subtitle/description (private `_price_parser`,
   `_attribute_parser`, `_text_parser`), brand from the title, category from the URL slug.
3. `CompatibilityExtractor.extract` / `RequirementExtractor.extract`: facts backed by literal catalog strings
   (`source=catalog`, `method=deterministic`).
4. `CompletenessAssessor.assess`: decides whether the product page must be fetched (`needs_web`).

`DatasetProfiler.profile` runs the same stages over the whole zip for `catalog-ingestion analyze`.
"""

from catalog_ingestion.preparation.compatibility_extractor import CompatibilityExtractor
from catalog_ingestion.preparation.completeness_assessor import CompletenessAssessor
from catalog_ingestion.preparation.dataset_profile import DatasetProfile
from catalog_ingestion.preparation.dataset_profiler import DatasetProfiler
from catalog_ingestion.preparation.load_error import LoadError
from catalog_ingestion.preparation.load_result import LoadResult
from catalog_ingestion.preparation.prepared_product import PreparedProduct
from catalog_ingestion.preparation.product_normalizer import ProductNormalizer
from catalog_ingestion.preparation.product_preparer import ProductPreparer
from catalog_ingestion.preparation.requirement_extractor import RequirementExtractor
from catalog_ingestion.preparation.zip_loader import ZipLoader

__all__ = [
    "CompatibilityExtractor",
    "CompletenessAssessor",
    "DatasetProfile",
    "DatasetProfiler",
    "LoadError",
    "LoadResult",
    "PreparedProduct",
    "ProductNormalizer",
    "ProductPreparer",
    "RequirementExtractor",
    "ZipLoader",
]
