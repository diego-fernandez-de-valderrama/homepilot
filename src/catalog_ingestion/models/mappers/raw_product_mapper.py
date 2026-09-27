from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from catalog_ingestion.models.domain import RawProduct
from catalog_ingestion.models.schemas import RawProductSchema


class RawProductMapper:
    @staticmethod
    def from_schema(schema: RawProductSchema, original: Mapping[str, Any]) -> RawProduct:
        """`original` is the untouched JSON; it is kept (read-only) for hashing and storage."""
        return RawProduct(
            id=schema.id,
            title=schema.title,
            subtitle=schema.subtitle,
            price=schema.price,
            variants=tuple(schema.variants),
            description=schema.description,
            attributes=schema.attributes,
            image=schema.image,
            url=schema.url,
            original=MappingProxyType(dict(original)),
        )
