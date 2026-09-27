import re
from typing import ClassVar

from catalog_ingestion.vocabulary._compatibility_terms import EXTRA_SURFACE_FORMS, TERMS
from catalog_ingestion.vocabulary.compatibility_term import CompatibilityTerm
from catalog_ingestion.vocabulary.enums import Dimension


class CompatibilityVocabulary:
    """Canonical compatibility vocabulary (dimensions ecosystem / voice_assistant / protocol / mobile_os).

    Aliases never cross concepts: "Apple Siri" is a voice assistant and does not imply
    Apple Home (HomeKit); "Google Assistant" does not imply Google Home; Matter is an
    interoperability standard (ecosystem dimension) and is not a transport protocol.
    A raw value without a safe mapping keeps `canonical_value=None`.
    """

    TERMS: ClassVar[tuple[CompatibilityTerm, ...]] = TERMS

    # Version suffixes on mobile OS values ("iOS 8.0 oder höher") are dropped for lookup.
    _OS_VERSION = re.compile(r"\s+\d+(\.\d+)*\s*(oder höher|or later|\+)?$", re.IGNORECASE)

    @staticmethod
    def normalize_alias(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold().replace("™", "").replace("®", "").strip()

    @staticmethod
    def lookup(value: str) -> CompatibilityTerm | None:
        """Canonical term for a raw value, or None when there is no safe mapping."""
        key = CompatibilityVocabulary.normalize_alias(value)
        if key in _BY_ALIAS:
            return _BY_ALIAS[key]
        stripped = CompatibilityVocabulary._OS_VERSION.sub("", key)
        term = _BY_ALIAS.get(stripped)
        if term is not None and term.dimension is Dimension.MOBILE_OS:
            return term
        return None

    @staticmethod
    def term_by_canonical(canonical: str | None) -> CompatibilityTerm | None:
        return _BY_CANONICAL.get(canonical) if canonical else None

    @staticmethod
    def label_for(canonical: str | None) -> str | None:
        term = CompatibilityVocabulary.term_by_canonical(canonical)
        return term.label if term else None

    @staticmethod
    def surface_forms(canonical: str) -> tuple[str, ...]:
        """Strings that may legitimately appear in evidence mentioning this canonical value."""
        term = _BY_CANONICAL[canonical]
        normalize = CompatibilityVocabulary.normalize_alias
        forms = {normalize(alias) for alias in term.aliases}
        forms.add(normalize(term.label))
        forms.update(EXTRA_SURFACE_FORMS.get(canonical, ()))
        return tuple(sorted(forms))

    @staticmethod
    def find_terms(text: str, dimension: Dimension) -> tuple[tuple[CompatibilityTerm, str], ...]:
        """Terms of one dimension named as whole words inside free text, with the matched text
        ("über Sprachsteuerung wie Google Assistant & Amazon Alexa" -> Google Assistant, Amazon Alexa)."""
        normalize = CompatibilityVocabulary.normalize_alias
        found: dict[str, tuple[CompatibilityTerm, str]] = {}
        for term in TERMS:
            if term.dimension is not dimension:
                continue
            for alias in sorted({normalize(a) for a in (*term.aliases, term.label)}, key=len, reverse=True):
                pattern = r"\s+".join(map(re.escape, alias.split()))
                match = re.search(rf"(?<!\w){pattern}(?!\w)", text, re.IGNORECASE)
                if match:
                    found.setdefault(term.canonical, (term, match.group(0)))
                    break
        return tuple(found.values())


_BY_CANONICAL = {term.canonical: term for term in TERMS}
# Canonical ids that are valid in several dimensions do not exist; alias keys are unique per dimension.
# Keys are normalized like lookups, so aliases written with "®" or "™" still match.
_BY_ALIAS: dict[str, CompatibilityTerm] = {
    CompatibilityVocabulary.normalize_alias(alias): term for term in TERMS for alias in (*term.aliases, term.canonical)
}
