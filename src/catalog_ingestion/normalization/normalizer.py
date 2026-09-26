"""RawProduct -> NormalizedProduct (deterministic, no I/O)."""

from urllib.parse import urlparse

from catalog_ingestion.domain.product import NormalizedProduct, RawProduct
from catalog_ingestion.normalization.attributes import parse_attributes
from catalog_ingestion.normalization.brand import detect_brand
from catalog_ingestion.normalization.price import parse_price
from catalog_ingestion.normalization.text import parse_description, parse_subtitle
from catalog_ingestion.vocabulary.categories import category_for_slug

_SMART_HOME_KEY = "Smart Home-fähig"


def category_slug_from_url(url: str) -> str | None:
    """`https://www.bauhaus.info/<category-slug>/<name-slug>/p/<id>` -> `<category-slug>`."""
    segments = [segment for segment in urlparse(url).path.split("/") if segment]
    if len(segments) >= 4 and segments[-2] == "p":
        return segments[0]
    return None


def _clean_url(value: str) -> str | None:
    value = value.strip()
    return value or None


def normalize(raw: RawProduct) -> NormalizedProduct:
    source_url = _clean_url(raw.url)
    attributes = parse_attributes(raw.attributes)
    slug = category_slug_from_url(source_url) if source_url else None
    category = category_for_slug(slug)

    smart_home_value = attributes.get(_SMART_HOME_KEY)
    is_smart_home = {"ja": True, "nein": False}.get(smart_home_value.casefold()) if smart_home_value else None

    return NormalizedProduct(
        id=raw.id.strip(),
        title=raw.title.strip(),
        subtitle=raw.subtitle.strip(),
        subtitle_parts=parse_subtitle(raw.subtitle.strip()),
        brand=detect_brand(raw.title.strip()),
        category_slug=slug,
        category=category.key if category else None,
        price=parse_price(raw.price),
        variants=tuple(variant.strip() for variant in raw.variants if variant.strip()),
        description=parse_description(raw.description),
        attributes=attributes,
        ean=attributes.get("EAN"),
        is_smart_home=is_smart_home,
        image_url=_clean_url(raw.image),
        source_url=source_url,
    )
