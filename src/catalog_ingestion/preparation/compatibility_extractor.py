import re
from typing import ClassVar

from catalog_ingestion.models import AttributeEntry, CompatibilityFact, Evidence, NormalizedProduct
from catalog_ingestion.preparation._attribute_parser import AttributeParser
from catalog_ingestion.vocabulary import CompatibilityVocabulary, Dimension, FactSource, FactStatus, Method


class CompatibilityExtractor:
    """Deterministic compatibility facts from catalog data (attributes, badges, title).

    Every fact produced here is backed by a literal catalog string, so it gets
    `source=catalog`, `method=deterministic` and a high confidence.
    """

    ATTRIBUTE_CONFIDENCE = 1.0
    TITLE_CONFIDENCE = 0.95

    # Attribute key -> dimension assumed for values without a canonical mapping.
    # `None` means the dimension is only known when the value maps to a canonical term.
    FIELD_DIMENSIONS: ClassVar[dict[str, Dimension | None]] = {
        "Unterstützte Sprachsteuerung": Dimension.VOICE_ASSISTANT,
        "Unterstützte Systeme": Dimension.ECOSYSTEM,
        "Datenübertragung": Dimension.PROTOCOL,
        "Unterstützte Betriebssysteme": Dimension.MOBILE_OS,
        "Systemvoraussetzung": Dimension.MOBILE_OS,
        "Smarte Steuerung": Dimension.CONTROL,
        "Anforderungen": None,  # mostly requirements; only mobile OS values become facts here
    }
    # "Philips Hue App + Google Home", "Samsung SmartThings und Aqara Home"
    _COMPOUND_SEPARATOR = re.compile(r"\s+\+\s+|\s+und\s+", re.IGNORECASE)
    # Only unambiguous technology names are read from titles.
    _TITLE_PATTERN = re.compile(r"\b(matter|wlan|wi-?fi|zigbee|bluetooth|z-wave)\b", re.IGNORECASE)
    _BADGE_VALUES = frozenset({"bluetooth"})

    @staticmethod
    def extract(product: NormalizedProduct) -> tuple[CompatibilityFact, ...]:
        return CompatibilityExtractor.dedupe(
            [
                *CompatibilityExtractor._attribute_facts(product),
                *CompatibilityExtractor._badge_facts(product),
                *CompatibilityExtractor._title_facts(product),
            ]
        )

    @staticmethod
    def dedupe(facts: list[CompatibilityFact]) -> tuple[CompatibilityFact, ...]:
        """Keep the first fact per (dimension, value); callers order facts by precedence."""
        seen: set[tuple[Dimension, str]] = set()
        unique: list[CompatibilityFact] = []
        for fact in facts:
            if fact.key in seen:
                continue
            seen.add(fact.key)
            unique.append(fact)
        return tuple(unique)

    @staticmethod
    def _values(entry: AttributeEntry) -> tuple[str, ...]:
        values = AttributeParser.split_values(entry.value)
        if entry.key == "Smarte Steuerung":
            separator = CompatibilityExtractor._COMPOUND_SEPARATOR
            values = tuple(part.strip() for value in values for part in separator.split(value) if part.strip())
        return values

    @staticmethod
    def _attribute_facts(product: NormalizedProduct) -> list[CompatibilityFact]:
        facts: list[CompatibilityFact] = []
        for entry in product.attributes.entries:
            if entry.key not in CompatibilityExtractor.FIELD_DIMENSIONS:
                continue
            default_dimension = CompatibilityExtractor.FIELD_DIMENSIONS[entry.key]
            evidence = Evidence(FactSource.CATALOG, f"{entry.key}: {entry.value}", field=f"attributes.{entry.key}")
            for value in CompatibilityExtractor._values(entry):
                term = CompatibilityVocabulary.lookup(value)
                if term is None and default_dimension is Dimension.CONTROL:
                    # "Per Smartphone oder über Sprachsteuerung wie Google Assistant & Amazon Alexa"
                    facts.extend(CompatibilityExtractor._embedded_voice_assistants(value, evidence))
                if default_dimension is None and (term is None or term.dimension is not Dimension.MOBILE_OS):
                    continue
                dimension = term.dimension if term else default_dimension or Dimension.CONTROL
                facts.append(
                    CompatibilityFact(
                        dimension=dimension,
                        raw_value=value,
                        canonical_value=term.canonical if term else None,
                        status=FactStatus.SUPPORTED,
                        evidence=evidence,
                        confidence=CompatibilityExtractor.ATTRIBUTE_CONFIDENCE,
                        method=Method.DETERMINISTIC,
                    )
                )
        return facts

    @staticmethod
    def _embedded_voice_assistants(value: str, evidence: Evidence) -> list[CompatibilityFact]:
        return [
            CompatibilityFact(
                dimension=term.dimension,
                raw_value=matched,
                canonical_value=term.canonical,
                status=FactStatus.SUPPORTED,
                evidence=evidence,
                confidence=CompatibilityExtractor.ATTRIBUTE_CONFIDENCE,
                method=Method.DETERMINISTIC,
            )
            for term, matched in CompatibilityVocabulary.find_terms(value, Dimension.VOICE_ASSISTANT)
        ]

    @staticmethod
    def _badge_facts(product: NormalizedProduct) -> list[CompatibilityFact]:
        facts: list[CompatibilityFact] = []
        for badge in product.attributes.badges:
            if badge.casefold() not in CompatibilityExtractor._BADGE_VALUES:
                continue
            term = CompatibilityVocabulary.lookup(badge)
            if term is None:
                continue
            facts.append(
                CompatibilityFact(
                    dimension=term.dimension,
                    raw_value=badge,
                    canonical_value=term.canonical,
                    status=FactStatus.SUPPORTED,
                    evidence=Evidence(FactSource.CATALOG, badge, field="attributes.badges"),
                    confidence=CompatibilityExtractor.ATTRIBUTE_CONFIDENCE,
                    method=Method.DETERMINISTIC,
                )
            )
        return facts

    @staticmethod
    def _title_facts(product: NormalizedProduct) -> list[CompatibilityFact]:
        facts: list[CompatibilityFact] = []
        for match in CompatibilityExtractor._TITLE_PATTERN.finditer(product.title):
            term = CompatibilityVocabulary.lookup(match.group(1))
            if term is None:
                continue
            facts.append(
                CompatibilityFact(
                    dimension=term.dimension,
                    raw_value=match.group(1),
                    canonical_value=term.canonical,
                    status=FactStatus.SUPPORTED,
                    evidence=Evidence(FactSource.CATALOG, product.title, field="title"),
                    confidence=CompatibilityExtractor.TITLE_CONFIDENCE,
                    method=Method.DETERMINISTIC,
                )
            )
        return facts
