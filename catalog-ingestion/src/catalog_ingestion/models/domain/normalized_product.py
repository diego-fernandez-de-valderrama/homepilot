from dataclasses import dataclass

from catalog_ingestion.models.domain.description import Description
from catalog_ingestion.models.domain.parsed_attributes import ParsedAttributes
from catalog_ingestion.models.domain.price import Price
from catalog_ingestion.models.domain.subtitle_parts import SubtitleParts


@dataclass(frozen=True, slots=True)
class NormalizedProduct:
    id: str
    title: str
    subtitle: str
    subtitle_parts: SubtitleParts
    brand: str | None
    category_slug: str | None
    category: str | None
    price: Price
    variants: tuple[str, ...]
    description: Description
    attributes: ParsedAttributes
    ean: str | None
    is_smart_home: bool | None
    image_url: str | None
    source_url: str | None
