from typing import ClassVar

from catalog_ingestion.core import Hashing
from catalog_ingestion.models import CompatibilityFact, EnrichedProduct, RetrievalDocument
from catalog_ingestion.vocabulary import (
    CategoryVocabulary,
    CompatibilityVocabulary,
    Dimension,
    FactStatus,
    RequirementVocabulary,
)


class RetrievalDocumentBuilder:
    """Builds the text that is embedded for semantic retrieval.

    The document is written for retrieval, not as a JSON dump. It holds the English
    canonical names (for English queries) next to the original German catalog terms
    (title, highlights, key attributes) for German queries.
    """

    DOCUMENT_VERSION = "1"  # part of the hash: bump to re-embed everything after a format change
    MAX_HIGHLIGHTS = 6
    # Catalog attributes that carry meaning for discovery queries (German keys, original values).
    KEY_ATTRIBUTES: ClassVar[tuple[str, ...]] = (
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
    _DIMENSION_TITLES: ClassVar[tuple[tuple[Dimension, str], ...]] = (
        (Dimension.ECOSYSTEM, "Smart home ecosystems and standards"),
        (Dimension.VOICE_ASSISTANT, "Voice assistants"),
        (Dimension.PROTOCOL, "Connectivity protocols"),
        (Dimension.CONTROL, "Apps and other control options"),
        (Dimension.MOBILE_OS, "Companion app platforms"),
    )

    @staticmethod
    def build(enriched: EnrichedProduct) -> RetrievalDocument:
        builder = RetrievalDocumentBuilder
        product = enriched.product
        category = CategoryVocabulary.by_key(enriched.category)
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
        lines.extend(builder._bullets("Key features", enriched.key_features))
        lines.extend(builder._bullets("Produkt-Highlights", product.description.highlights[: builder.MAX_HIGHLIGHTS]))

        for dimension, title in builder._DIMENSION_TITLES:
            names = builder._names(enriched, dimension, FactStatus.SUPPORTED)
            if names:
                lines.append(f"{title}: {', '.join(names)}")
        unsupported = sorted(
            {builder._fact_name(f) for f in enriched.compatibility if f.status is FactStatus.UNSUPPORTED}
        )
        if unsupported:
            lines.append(f"Not compatible with: {', '.join(unsupported)}")

        lines.extend(builder._bullets("Requirements", builder._requirement_lines(enriched)))
        lines.extend(builder._bullets("Use cases", enriched.use_cases))

        specs = [f"{spec.name}: {spec.value}" for spec in enriched.specs]
        specs.extend(
            f"{key}: {value}" for key in builder.KEY_ATTRIBUTES if (value := product.attributes.get(key)) is not None
        )
        lines.extend(builder._bullets("Specifications", list(dict.fromkeys(specs))))

        if product.price.value is not None:
            lines.append(f"Price: {product.price.value} {product.price.currency or ''}".rstrip())

        text = "\n".join(lines)
        doc_hash = Hashing.sha256_text(f"{builder.DOCUMENT_VERSION}\n{text}")
        return RetrievalDocument(product_id=product.id, text=text, doc_hash=doc_hash)

    @staticmethod
    def _requirement_lines(enriched: EnrichedProduct) -> list[str]:
        lines = []
        for requirement in enriched.requirements:
            options = [
                (term.label if (term := RequirementVocabulary.term_by_canonical(alt)) else alt)
                for alt in requirement.alternatives
                if alt != requirement.canonical_item
            ]
            term = RequirementVocabulary.term_by_canonical(requirement.canonical_item)
            label = term.label if term else requirement.item
            suffix = f" (or: {', '.join(options)})" if options else ""
            lines.append(f"{label} - {requirement.necessity.value.replace('_', ' ')}{suffix}")
        return lines

    @staticmethod
    def _fact_name(fact: CompatibilityFact) -> str:
        return CompatibilityVocabulary.label_for(fact.canonical_value) or fact.raw_value

    @staticmethod
    def _names(enriched: EnrichedProduct, dimension: Dimension, status: FactStatus) -> list[str]:
        return sorted(
            {
                RetrievalDocumentBuilder._fact_name(f)
                for f in enriched.compatibility
                if f.dimension is dimension and f.status is status
            }
        )

    @staticmethod
    def _bullets(title: str, items: list[str] | tuple[str, ...]) -> list[str]:
        return [f"{title}:", *(f"- {item}" for item in items)] if items else []
