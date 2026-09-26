"""Deterministic requirements from catalog attributes.

Sources: `Anforderungen` (explicit requirement list), `Hinweise` (free-text notes
such as "Steuerung nur in Verbindung mit dem Bosch Smart Home Controller möglich")
and `Installationshinweis` (professional installation).
"""

import re

from catalog_ingestion.domain.enums import (
    Dimension,
    FactSource,
    Method,
    Necessity,
    RequirementKind,
)
from catalog_ingestion.domain.facts import Evidence, Requirement
from catalog_ingestion.domain.product import AttributeEntry, NormalizedProduct
from catalog_ingestion.normalization.attributes import split_values
from catalog_ingestion.vocabulary import compatibility as compat_vocab
from catalog_ingestion.vocabulary import requirements as vocab

CONFIDENCE = 1.0
_TRIGGER = re.compile(
    r"nur in (verbindung|kombination)|erfordert|erforderlich|notwendig|voraus|anforderung|benötigt|zu installieren",
    re.IGNORECASE,
)
_PARTIAL = re.compile(r"für (manche|einige|erweiterte) funktionen", re.IGNORECASE)
# Parenthesised negative remarks ("(nicht enthalten)", "(nicht mehr kompatibel mit der Zentrale CCU2)")
# are removed before matching so they neither trigger nor cancel a requirement.
_NEGATIVE_CLAUSE = re.compile(r"\([^)]*nicht (mehr kompatibel|enthalten)[^)]*\)", re.IGNORECASE)
_NEGATIVE_NOTE = re.compile(r"^\s*nicht mehr kompatibel", re.IGNORECASE)
_HUB_KINDS = {RequirementKind.HUB, RequirementKind.GATEWAY}


def _evidence(entry: AttributeEntry) -> Evidence:
    return Evidence(FactSource.CATALOG, f"{entry.key}: {entry.value}", field=f"attributes.{entry.key}")


def _from_requirement_list(entry: AttributeEntry) -> list[Requirement]:
    requirements: list[Requirement] = []
    for value in split_values(entry.value):
        compat_term = compat_vocab.lookup(value)
        if compat_term is not None and compat_term.dimension is Dimension.MOBILE_OS:
            continue  # handled as a mobile OS compatibility fact
        term = vocab.lookup(value)
        requirements.append(
            Requirement(
                item=value,
                canonical_item=term.canonical if term else None,
                kind=term.kind if term else RequirementKind.OTHER,
                necessity=Necessity.REQUIRED,
                alternatives=(term.canonical,) if term else (),
                evidence=_evidence(entry),
                confidence=CONFIDENCE,
                method=Method.DETERMINISTIC,
            )
        )
    return requirements


def _from_note(entry: AttributeEntry) -> list[Requirement]:
    text = _NEGATIVE_CLAUSE.sub("", entry.value)
    terms = vocab.match_terms(text)
    installation = [term for term in terms if term.kind is RequirementKind.PROFESSIONAL_INSTALLATION]
    requirements: list[Requirement] = [
        Requirement(
            item=term.label,
            canonical_item=term.canonical,
            kind=term.kind,
            necessity=Necessity.REQUIRED,
            alternatives=(term.canonical,),
            evidence=_evidence(entry),
            confidence=CONFIDENCE,
            method=Method.DETERMINISTIC,
        )
        for term in installation
    ]
    if not _TRIGGER.search(text) or _NEGATIVE_NOTE.search(text):
        return requirements

    others = [term for term in terms if term.kind is not RequirementKind.PROFESSIONAL_INSTALLATION]
    if not others:
        return requirements
    necessity = Necessity.REQUIRED_FOR_SOME_FEATURES if _PARTIAL.search(text) else Necessity.REQUIRED
    primary = others[0]
    if primary.kind in _HUB_KINDS:
        # "Access Point; Zentrale CCU3; Partnerlösungen" -> one requirement, any alternative satisfies it.
        group = [term for term in others if term.kind in _HUB_KINDS or term.canonical == "standalone"]
    else:
        group = [primary]
    requirements.append(
        Requirement(
            item=primary.label,
            canonical_item=primary.canonical,
            kind=primary.kind,
            necessity=necessity,
            alternatives=tuple(term.canonical for term in group),
            evidence=_evidence(entry),
            confidence=CONFIDENCE,
            method=Method.DETERMINISTIC,
        )
    )
    return requirements


def dedupe_requirements(requirements: list[Requirement]) -> tuple[Requirement, ...]:
    seen: set[str] = set()
    unique: list[Requirement] = []
    for requirement in requirements:
        if requirement.key in seen:
            continue
        seen.add(requirement.key)
        unique.append(requirement)
    return tuple(unique)


def extract_requirements(product: NormalizedProduct) -> tuple[Requirement, ...]:
    requirements: list[Requirement] = []
    for entry in product.attributes.entries:
        if entry.key == "Anforderungen":
            requirements.extend(_from_requirement_list(entry))
        elif entry.key in ("Hinweise", "Installationshinweis"):
            requirements.extend(_from_note(entry))
    return dedupe_requirements(requirements)
