"""Deterministic compatibility facts from catalog data (attributes, badges, title).

Every fact produced here is backed by a literal catalog string, so it gets
`source=catalog`, `method=deterministic` and a high confidence.
"""

import re

from catalog_ingestion.domain.enums import Dimension, FactSource, FactStatus, Method
from catalog_ingestion.domain.facts import CompatibilityFact, Evidence
from catalog_ingestion.domain.product import AttributeEntry, NormalizedProduct
from catalog_ingestion.normalization.attributes import split_values
from catalog_ingestion.vocabulary import compatibility as vocab

ATTRIBUTE_CONFIDENCE = 1.0
TITLE_CONFIDENCE = 0.95

# Attribute key -> dimension assumed for values without a canonical mapping.
# `None` means the dimension is only known when the value maps to a canonical term.
FIELD_DIMENSIONS: dict[str, Dimension | None] = {
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
_BADGE_VALUES = {"bluetooth"}


def _values(entry: AttributeEntry) -> tuple[str, ...]:
    values = split_values(entry.value)
    if entry.key == "Smarte Steuerung":
        values = tuple(part.strip() for value in values for part in _COMPOUND_SEPARATOR.split(value) if part.strip())
    return values


def _attribute_facts(product: NormalizedProduct) -> list[CompatibilityFact]:
    facts: list[CompatibilityFact] = []
    for entry in product.attributes.entries:
        if entry.key not in FIELD_DIMENSIONS:
            continue
        default_dimension = FIELD_DIMENSIONS[entry.key]
        evidence = Evidence(FactSource.CATALOG, f"{entry.key}: {entry.value}", field=f"attributes.{entry.key}")
        for value in _values(entry):
            term = vocab.lookup(value)
            if term is None and default_dimension is Dimension.CONTROL:
                # "Per Smartphone oder über Sprachsteuerung wie Google Assistant & Amazon Alexa"
                facts.extend(_embedded_voice_assistants(value, evidence))
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
                    confidence=ATTRIBUTE_CONFIDENCE,
                    method=Method.DETERMINISTIC,
                )
            )
    return facts


def _embedded_voice_assistants(value: str, evidence: Evidence) -> list[CompatibilityFact]:
    return [
        CompatibilityFact(
            dimension=term.dimension,
            raw_value=matched,
            canonical_value=term.canonical,
            status=FactStatus.SUPPORTED,
            evidence=evidence,
            confidence=ATTRIBUTE_CONFIDENCE,
            method=Method.DETERMINISTIC,
        )
        for term, matched in vocab.find_terms(value, Dimension.VOICE_ASSISTANT)
    ]


def _badge_facts(product: NormalizedProduct) -> list[CompatibilityFact]:
    facts: list[CompatibilityFact] = []
    for badge in product.attributes.badges:
        if badge.casefold() not in _BADGE_VALUES:
            continue
        term = vocab.lookup(badge)
        if term is None:
            continue
        facts.append(
            CompatibilityFact(
                dimension=term.dimension,
                raw_value=badge,
                canonical_value=term.canonical,
                status=FactStatus.SUPPORTED,
                evidence=Evidence(FactSource.CATALOG, badge, field="attributes.badges"),
                confidence=ATTRIBUTE_CONFIDENCE,
                method=Method.DETERMINISTIC,
            )
        )
    return facts


def _title_facts(product: NormalizedProduct) -> list[CompatibilityFact]:
    facts: list[CompatibilityFact] = []
    for match in _TITLE_PATTERN.finditer(product.title):
        term = vocab.lookup(match.group(1))
        if term is None:
            continue
        facts.append(
            CompatibilityFact(
                dimension=term.dimension,
                raw_value=match.group(1),
                canonical_value=term.canonical,
                status=FactStatus.SUPPORTED,
                evidence=Evidence(FactSource.CATALOG, product.title, field="title"),
                confidence=TITLE_CONFIDENCE,
                method=Method.DETERMINISTIC,
            )
        )
    return facts


def dedupe_facts(facts: list[CompatibilityFact]) -> tuple[CompatibilityFact, ...]:
    """Keep the first fact per (dimension, value); callers order facts by precedence."""
    seen: set[tuple[Dimension, str]] = set()
    unique: list[CompatibilityFact] = []
    for fact in facts:
        if fact.key in seen:
            continue
        seen.add(fact.key)
        unique.append(fact)
    return tuple(unique)


def extract_compatibility(product: NormalizedProduct) -> tuple[CompatibilityFact, ...]:
    return dedupe_facts([*_attribute_facts(product), *_badge_facts(product), *_title_facts(product)])
