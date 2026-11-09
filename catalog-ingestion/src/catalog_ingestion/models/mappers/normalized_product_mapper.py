from catalog_ingestion.models.domain import (
    AttributeEntry,
    Description,
    NormalizedProduct,
    ParsedAttributes,
    Price,
    SubtitleParts,
)
from catalog_ingestion.models.mappers._number_conversion import NumberConversion
from catalog_ingestion.models.schemas import AttributeSchema, KeyValueSchema, NormalizedProductSchema, PriceSchema


class NormalizedProductMapper:
    @staticmethod
    def price_to_schema(price: Price) -> PriceSchema:
        return PriceSchema(
            value=NumberConversion.to_float(price.value),
            currency=price.currency,
            original_value=NumberConversion.to_float(price.original_value),
            savings=NumberConversion.to_float(price.savings),
            raw=price.raw,
        )

    @staticmethod
    def to_schema(product: NormalizedProduct) -> NormalizedProductSchema:
        return NormalizedProductSchema(
            id=product.id,
            title=product.title,
            subtitle=product.subtitle,
            subtitle_features=list(product.subtitle_parts.features),
            subtitle_properties=[KeyValueSchema(key=k, value=v) for k, v in product.subtitle_parts.properties],
            brand=product.brand,
            category_slug=product.category_slug,
            category=product.category,
            price=NormalizedProductMapper.price_to_schema(product.price),
            variants=list(product.variants),
            description_highlights=list(product.description.highlights),
            description_text=product.description.text,
            badges=list(product.attributes.badges),
            attributes=[
                AttributeSchema(section=e.section, key=e.key, value=e.value) for e in product.attributes.entries
            ],
            unparsed_attribute_lines=list(product.attributes.unparsed_lines),
            ean=product.ean,
            is_smart_home=product.is_smart_home,
            image_url=product.image_url,
            source_url=product.source_url,
        )

    @staticmethod
    def from_schema(schema: NormalizedProductSchema) -> NormalizedProduct:
        return NormalizedProduct(
            id=schema.id,
            title=schema.title,
            subtitle=schema.subtitle,
            subtitle_parts=SubtitleParts(
                features=tuple(schema.subtitle_features),
                properties=tuple((kv.key, kv.value) for kv in schema.subtitle_properties),
            ),
            brand=schema.brand,
            category_slug=schema.category_slug,
            category=schema.category,
            price=Price(
                value=NumberConversion.to_decimal(schema.price.value),
                currency=schema.price.currency,
                original_value=NumberConversion.to_decimal(schema.price.original_value),
                savings=NumberConversion.to_decimal(schema.price.savings),
                raw=schema.price.raw,
            ),
            variants=tuple(schema.variants),
            description=Description(highlights=tuple(schema.description_highlights), text=schema.description_text),
            attributes=ParsedAttributes(
                badges=tuple(schema.badges),
                entries=tuple(AttributeEntry(a.section, a.key, a.value) for a in schema.attributes),
                unparsed_lines=tuple(schema.unparsed_attribute_lines),
            ),
            ean=schema.ean,
            is_smart_home=schema.is_smart_home,
            image_url=schema.image_url,
            source_url=schema.source_url,
        )
