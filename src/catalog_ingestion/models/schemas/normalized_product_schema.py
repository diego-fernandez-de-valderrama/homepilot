from pydantic import BaseModel

from catalog_ingestion.models.schemas.attribute_schema import AttributeSchema
from catalog_ingestion.models.schemas.key_value_schema import KeyValueSchema
from catalog_ingestion.models.schemas.price_schema import PriceSchema


class NormalizedProductSchema(BaseModel):
    id: str
    title: str
    subtitle: str
    subtitle_features: list[str]
    subtitle_properties: list[KeyValueSchema]
    brand: str | None
    category_slug: str | None
    category: str | None
    price: PriceSchema
    variants: list[str]
    description_highlights: list[str]
    description_text: str
    badges: list[str]
    attributes: list[AttributeSchema]
    unparsed_attribute_lines: list[str]
    ean: str | None
    is_smart_home: bool | None
    image_url: str | None
    source_url: str | None
