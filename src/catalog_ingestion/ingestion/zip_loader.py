"""Reads product JSON files from the dataset zip.

The zip contains `info/<id>.json` plus macOS metadata (`__MACOSX/`, `._*`) that is skipped.
Invalid files are reported through `LoadError`s instead of stopping the run.
"""

import json
import logging
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from catalog_ingestion.core.logging import log_fields
from catalog_ingestion.domain.product import RawProduct
from catalog_ingestion.schemas.mappers import raw_from_schema
from catalog_ingestion.schemas.raw_product import RawProductSchema

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadError:
    member: str
    error: str
    duplicate: bool = False  # the product itself was loaded from another member


@dataclass(frozen=True, slots=True)
class LoadResult:
    products: tuple[RawProduct, ...]
    errors: tuple[LoadError, ...]


def _is_product_member(name: str) -> bool:
    path = PurePosixPath(name)
    if name.endswith("/") or path.suffix.lower() != ".json":
        return False
    return not any(part == "__MACOSX" or part.startswith("._") for part in path.parts)


def iter_members(zip_path: Path) -> Iterator[tuple[str, bytes]]:
    with zipfile.ZipFile(zip_path) as archive:
        for name in sorted(archive.namelist()):
            if _is_product_member(name):
                yield name, archive.read(name)


def load_products(zip_path: Path) -> LoadResult:
    products: dict[str, RawProduct] = {}
    errors: list[LoadError] = []
    for name, payload in iter_members(zip_path):
        try:
            data = json.loads(payload.decode("utf-8"))
            schema = RawProductSchema.model_validate(data)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            errors.append(LoadError(name, str(exc)))
            logger.warning("Skipping invalid product file", extra=log_fields(member=name, error=str(exc)))
            continue
        product = raw_from_schema(schema, original=data)
        if product.id in products:
            errors.append(LoadError(name, f"duplicate product id {product.id}", duplicate=True))
            logger.warning("Duplicate product id, keeping first", extra=log_fields(member=name, product_id=product.id))
            continue
        products[product.id] = product
    return LoadResult(products=tuple(products.values()), errors=tuple(errors))
