"""Evidence read straight from the catalog JSON (deterministic parsing, confidence 1.0)."""

from catalog_ingestion.domain.enums import FactSource, Method

from smart_home_agent.models import Evidence, Product

# Fields copied verbatim from the catalog JSON by deterministic parsing.
CATALOG_FIELDS = {"price", "title", "ean", "image", "url"}
# Topic aliases -> provenance field names used by catalog-ingestion.
FIELD_ALIASES = {
    "summary": ("summary_en", "summary_de"),
    "description": ("summary_en", "summary_de"),
    "features": ("key_features",),
    "type": ("product_type",),
    "specifications": ("specs",),
}


def catalog_field(product: Product, topic: str) -> list[Evidence]:
    value = {
        "price": product.price_raw,
        "title": product.title,
        "ean": product.ean,
        "image": product.image_url,
        "url": product.source_url,
    }[topic]
    return [
        Evidence(source=FactSource.CATALOG, text=value or "", field=topic, method=Method.DETERMINISTIC, confidence=1.0)
    ]


def attribute(product: Product, topic: str) -> list[Evidence]:
    return [
        Evidence(
            source=FactSource.CATALOG,
            text=f"{key}: {value}",
            field=f"attributes.{section}.{key}",
            method=Method.DETERMINISTIC,
            confidence=1.0,
        )
        for section, entries in product.attributes.items()
        for key, value in entries.items()
        if key.casefold() == topic
    ]
