import re

from catalog_ingestion.models import AttributeEntry, Evidence, NormalizedProduct, Requirement
from catalog_ingestion.preparation._attribute_parser import AttributeParser
from catalog_ingestion.vocabulary import (
    CompatibilityVocabulary,
    Dimension,
    FactSource,
    Method,
    Necessity,
    RequirementKind,
    RequirementVocabulary,
)


class RequirementExtractor:
    """Deterministic requirements from catalog attributes.

    Sources: `Anforderungen` (explicit requirement list), `Hinweise` (free-text notes
    such as "Steuerung nur in Verbindung mit dem Bosch Smart Home Controller möglich")
    and `Installationshinweis` (professional installation).
    """

    CONFIDENCE = 1.0
    _TRIGGER = re.compile(
        r"nur in (verbindung|kombination)|erfordert|erforderlich|notwendig|voraus|anforderung|benötigt"
        r"|zu installieren",
        re.IGNORECASE,
    )
    _PARTIAL = re.compile(r"für (manche|einige|erweiterte) funktionen", re.IGNORECASE)
    # Parenthesised negative remarks ("(nicht enthalten)", "(nicht mehr kompatibel mit der Zentrale CCU2)")
    # are removed before matching so they neither trigger nor cancel a requirement.
    _NEGATIVE_CLAUSE = re.compile(r"\([^)]*nicht (mehr kompatibel|enthalten)[^)]*\)", re.IGNORECASE)
    _NEGATIVE_NOTE = re.compile(r"^\s*nicht mehr kompatibel", re.IGNORECASE)
    _HUB_KINDS = frozenset({RequirementKind.HUB, RequirementKind.GATEWAY})

    @staticmethod
    def extract(product: NormalizedProduct) -> tuple[Requirement, ...]:
        requirements: list[Requirement] = []
        for entry in product.attributes.entries:
            if entry.key == "Anforderungen":
                requirements.extend(RequirementExtractor._from_requirement_list(entry))
            elif entry.key in ("Hinweise", "Installationshinweis"):
                requirements.extend(RequirementExtractor._from_note(entry))
        return RequirementExtractor.dedupe(requirements)

    @staticmethod
    def dedupe(requirements: list[Requirement]) -> tuple[Requirement, ...]:
        seen: set[str] = set()
        unique: list[Requirement] = []
        for requirement in requirements:
            if requirement.key in seen:
                continue
            seen.add(requirement.key)
            unique.append(requirement)
        return tuple(unique)

    @staticmethod
    def _evidence(entry: AttributeEntry) -> Evidence:
        return Evidence(FactSource.CATALOG, f"{entry.key}: {entry.value}", field=f"attributes.{entry.key}")

    @staticmethod
    def _from_requirement_list(entry: AttributeEntry) -> list[Requirement]:
        requirements: list[Requirement] = []
        for value in AttributeParser.split_values(entry.value):
            compat_term = CompatibilityVocabulary.lookup(value)
            if compat_term is not None and compat_term.dimension is Dimension.MOBILE_OS:
                continue  # handled as a mobile OS compatibility fact
            term = RequirementVocabulary.lookup(value)
            requirements.append(
                Requirement(
                    item=value,
                    canonical_item=term.canonical if term else None,
                    kind=term.kind if term else RequirementKind.OTHER,
                    necessity=Necessity.REQUIRED,
                    alternatives=(term.canonical,) if term else (),
                    evidence=RequirementExtractor._evidence(entry),
                    confidence=RequirementExtractor.CONFIDENCE,
                    method=Method.DETERMINISTIC,
                )
            )
        return requirements

    @staticmethod
    def _from_note(entry: AttributeEntry) -> list[Requirement]:
        text = RequirementExtractor._NEGATIVE_CLAUSE.sub("", entry.value)
        terms = RequirementVocabulary.match_terms(text)
        installation = [term for term in terms if term.kind is RequirementKind.PROFESSIONAL_INSTALLATION]
        requirements: list[Requirement] = [
            Requirement(
                item=term.label,
                canonical_item=term.canonical,
                kind=term.kind,
                necessity=Necessity.REQUIRED,
                alternatives=(term.canonical,),
                evidence=RequirementExtractor._evidence(entry),
                confidence=RequirementExtractor.CONFIDENCE,
                method=Method.DETERMINISTIC,
            )
            for term in installation
        ]
        if not RequirementExtractor._TRIGGER.search(text) or RequirementExtractor._NEGATIVE_NOTE.search(text):
            return requirements

        others = [term for term in terms if term.kind is not RequirementKind.PROFESSIONAL_INSTALLATION]
        if not others:
            return requirements
        partial = RequirementExtractor._PARTIAL.search(text)
        necessity = Necessity.REQUIRED_FOR_SOME_FEATURES if partial else Necessity.REQUIRED
        primary = others[0]
        hub_kinds = RequirementExtractor._HUB_KINDS
        if primary.kind in hub_kinds:
            # "Access Point; Zentrale CCU3; Partnerlösungen" -> one requirement, any alternative satisfies it.
            group = [term for term in others if term.kind in hub_kinds or term.canonical == "standalone"]
        else:
            group = [primary]
        requirements.append(
            Requirement(
                item=primary.label,
                canonical_item=primary.canonical,
                kind=primary.kind,
                necessity=necessity,
                alternatives=tuple(term.canonical for term in group),
                evidence=RequirementExtractor._evidence(entry),
                confidence=RequirementExtractor.CONFIDENCE,
                method=Method.DETERMINISTIC,
            )
        )
        return requirements
