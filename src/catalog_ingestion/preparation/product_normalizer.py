from urllib.parse import urlparse

from catalog_ingestion.models import NormalizedProduct, RawProduct
from catalog_ingestion.preparation._attribute_parser import AttributeParser
from catalog_ingestion.preparation._price_parser import PriceParser
from catalog_ingestion.preparation._text_parser import TextParser
from catalog_ingestion.vocabulary import BrandVocabulary, CategoryVocabulary


class ProductNormalizer:
    """RawProduct -> NormalizedProduct (deterministic, no I/O): price, attributes blob, subtitle and
    description, brand from the title, category from the URL slug."""

    _SMART_HOME_KEY = "Smart Home-fähig"

    @staticmethod
    def normalize(raw: RawProduct) -> NormalizedProduct:
        source_url = ProductNormalizer._clean_url(raw.url)
        attributes = AttributeParser.parse(raw.attributes)
        slug = ProductNormalizer.category_slug_from_url(source_url) if source_url else None
        category = CategoryVocabulary.for_slug(slug)

        smart_home_value = attributes.get(ProductNormalizer._SMART_HOME_KEY)
        is_smart_home = {"ja": True, "nein": False}.get(smart_home_value.casefold()) if smart_home_value else None

        return NormalizedProduct(
            id=raw.id.strip(),
            title=raw.title.strip(),
            subtitle=raw.subtitle.strip(),
            subtitle_parts=TextParser.parse_subtitle(raw.subtitle.strip()),
            brand=BrandVocabulary.detect(raw.title.strip()),
            category_slug=slug,
            category=category.key if category else None,
            price=PriceParser.parse(raw.price),
            variants=tuple(variant.strip() for variant in raw.variants if variant.strip()),
            description=TextParser.parse_description(raw.description),
            attributes=attributes,
            ean=attributes.get("EAN"),
            is_smart_home=is_smart_home,
            image_url=ProductNormalizer._clean_url(raw.image),
            source_url=source_url,
        )

    @staticmethod
    def category_slug_from_url(url: str) -> str | None:
        """`https://www.bauhaus.info/<category-slug>/<name-slug>/p/<id>` -> `<category-slug>`."""
        segments = [segment for segment in urlparse(url).path.split("/") if segment]
        if len(segments) >= 4 and segments[-2] == "p":
            return segments[0]
        return None

    @staticmethod
    def _clean_url(value: str) -> str | None:
        value = value.strip()
        return value or None
