"""Provenance lookup: where a product fact or field value comes from. Only stored evidence is returned."""

from catalog_ingestion.domain.enums import FactSource, Method

from smart_home_agent.models.evidence import Evidence, EvidenceResult
from smart_home_agent.models.product import Product
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services import vocabulary
from smart_home_agent.services.compatibility import ProductNotFoundError
from smart_home_agent.services.vocabulary import TermResolutionError

# Fields copied verbatim from the catalog JSON by deterministic parsing.
_CATALOG_FIELDS = {"price", "title", "ean", "image", "url"}
# Topic aliases -> provenance field names used by catalog-ingestion.
_FIELD_ALIASES = {
    "summary": ("summary_en", "summary_de"),
    "description": ("summary_en", "summary_de"),
    "features": ("key_features",),
    "type": ("product_type",),
    "specifications": ("specs",),
}
TOPICS_HELP = (
    "a compatibility term (e.g. 'Matter', 'HomeKit', 'Zigbee'), 'requirements', a field "
    "(price, title, brand, category, product_type, summary, key_features, use_cases, specs) or a catalog attribute name"
)


def _catalog_field(product: Product, topic: str) -> list[Evidence]:
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


def _attribute(product: Product, topic: str) -> list[Evidence]:
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


def evidence_for(product: Product, topic: str) -> EvidenceResult:
    key = topic.strip().casefold()
    result = EvidenceResult(product_id=product.id, title=product.title, topic=topic, items=[], provenance=[])

    if key in ("requirements", "requirement", "anforderungen"):
        result.items = [r.evidence for r in product.requirements]
        result.note = None if result.items else "The catalog lists no requirements for this product."
        return result
    if key in _CATALOG_FIELDS:
        result.items = _catalog_field(product, key)
        return result
    fields = _FIELD_ALIASES.get(key, (key,))
    provenance = [p for p in product.provenance if p.field in fields]
    if provenance:
        result.provenance = provenance
        return result
    attributes = _attribute(product, key)
    if attributes:
        result.items = attributes
        return result
    try:
        resolved = vocabulary.resolve_term(topic)
    except TermResolutionError as exc:
        if exc.options:
            raise
        raise TermResolutionError("evidence topic", topic, []) from exc
    result.items = [fact.evidence for fact in product.facts_for(resolved.canonical)]
    if not result.items:
        result.note = (
            f"The catalog has no evidence about {resolved.label} for this product: its compatibility is unknown."
        )
    return result


class EvidenceService:
    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog

    def get(self, product_id: str, topic: str) -> EvidenceResult:
        products = self._catalog.get_products([product_id])
        if not products:
            raise ProductNotFoundError([product_id])
        return evidence_for(products[0], topic)
