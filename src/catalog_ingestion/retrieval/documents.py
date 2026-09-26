"""Builds the text that is embedded for semantic retrieval.

The document is written for retrieval, not as a JSON dump. It holds the English
canonical names (for English queries) next to the original German catalog terms
(title, highlights, key attributes) for German queries.
"""

from dataclasses import dataclass

from catalog_ingestion.core.hashing import sha256_text
from catalog_ingestion.domain.enrichment import EnrichedProduct
from catalog_ingestion.domain.enums import Dimension, FactStatus
from catalog_ingestion.domain.facts import CompatibilityFact
from catalog_ingestion.vocabulary.categories import category_by_key
from catalog_ingestion.vocabulary.compatibility import label_for
from catalog_ingestion.vocabulary.requirements import term_by_canonical

DOCUMENT_VERSION = "1"
MAX_HIGHLIGHTS = 6
# Catalog attributes that carry meaning for discovery queries (German keys, original values).
KEY_ATTRIBUTES: tuple[str, ...] = (
    "Funktionen",
    "Ausstattung",
    "Geeignet für",
    "Passend für",
    "Einsatzbereich",
    "Anwendungsbereich",
    "Betriebsart",
    "Stromversorgung",
    "Lampensockel",
    "Lichtfarbe",
    "Lichtstrom",
    "Leistung",
    "Auflösung",
    "Alarmierungsmöglichkeiten",
    "Schutzart",
    "Farbe",
)
_DIMENSION_TITLES: tuple[tuple[Dimension, str], ...] = (
    (Dimension.ECOSYSTEM, "Smart home ecosystems and standards"),
    (Dimension.VOICE_ASSISTANT, "Voice assistants"),
    (Dimension.PROTOCOL, "Connectivity protocols"),
    (Dimension.CONTROL, "Apps and other control options"),
    (Dimension.MOBILE_OS, "Companion app platforms"),
)


@dataclass(frozen=True, slots=True)
class RetrievalDocument:
    product_id: str
    text: str
    doc_hash: str


def _fact_name(fact: CompatibilityFact) -> str:
    return label_for(fact.canonical_value) or fact.raw_value


def _names(enriched: EnrichedProduct, dimension: Dimension, status: FactStatus) -> list[str]:
    names = {_fact_name(f) for f in enriched.compatibility if f.dimension is dimension and f.status is status}
    return sorted(names)


def _bullets(title: str, items: list[str] | tuple[str, ...]) -> list[str]:
    return [f"{title}:", *(f"- {item}" for item in items)] if items else []


def build_document(enriched: EnrichedProduct) -> RetrievalDocument:
    product = enriched.product
    category = category_by_key(enriched.category)
    lines: list[str] = [f"Product: {product.title}"]
    if enriched.brand:
        lines.append(f"Brand: {enriched.brand}")
    if category:
        lines.append(f"Category: {category.label_en} ({category.label_de})")
    if enriched.product_type:
        lines.append(f"Product type: {enriched.product_type}")
    if product.subtitle:
        lines.append(f"Details: {product.subtitle}")
    if enriched.summary_en:
        lines.append(f"Summary: {enriched.summary_en}")
    if enriched.summary_de:
        lines.append(f"Zusammenfassung: {enriched.summary_de}")
    lines.extend(_bullets("Key features", enriched.key_features))
    lines.extend(_bullets("Produkt-Highlights", product.description.highlights[:MAX_HIGHLIGHTS]))

    for dimension, title in _DIMENSION_TITLES:
        names = _names(enriched, dimension, FactStatus.SUPPORTED)
        if names:
            lines.append(f"{title}: {', '.join(names)}")
    unsupported = sorted({_fact_name(f) for f in enriched.compatibility if f.status is FactStatus.UNSUPPORTED})
    if unsupported:
        lines.append(f"Not compatible with: {', '.join(unsupported)}")

    requirement_lines = []
    for requirement in enriched.requirements:
        options = [
            (term.label if (term := term_by_canonical(alt)) else alt)
            for alt in requirement.alternatives
            if alt != requirement.canonical_item
        ]
        label = term.label if (term := term_by_canonical(requirement.canonical_item)) else requirement.item
        suffix = f" (or: {', '.join(options)})" if options else ""
        requirement_lines.append(f"{label} - {requirement.necessity.value.replace('_', ' ')}{suffix}")
    lines.extend(_bullets("Requirements", requirement_lines))
    lines.extend(_bullets("Use cases", enriched.use_cases))

    specs = [f"{spec.name}: {spec.value}" for spec in enriched.specs]
    specs.extend(f"{key}: {value}" for key in KEY_ATTRIBUTES if (value := product.attributes.get(key)) is not None)
    lines.extend(_bullets("Specifications", list(dict.fromkeys(specs))))

    if product.price.value is not None:
        lines.append(f"Price: {product.price.value} {product.price.currency or ''}".rstrip())

    text = "\n".join(lines)
    return RetrievalDocument(product_id=product.id, text=text, doc_hash=sha256_text(f"{DOCUMENT_VERSION}\n{text}"))
