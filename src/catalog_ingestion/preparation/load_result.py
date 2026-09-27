from dataclasses import dataclass

from catalog_ingestion.models import RawProduct
from catalog_ingestion.preparation.load_error import LoadError


@dataclass(frozen=True, slots=True)
class LoadResult:
    products: tuple[RawProduct, ...]
    errors: tuple[LoadError, ...]
