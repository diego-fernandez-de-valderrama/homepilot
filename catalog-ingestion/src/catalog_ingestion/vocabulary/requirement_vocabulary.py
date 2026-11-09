from typing import ClassVar

from catalog_ingestion.vocabulary._requirement_terms import TERMS
from catalog_ingestion.vocabulary.enums import RequirementKind
from catalog_ingestion.vocabulary.requirement_term import RequirementTerm


class RequirementVocabulary:
    """Canonical requirement items (hubs, gateways, subscriptions, ...) and their text patterns."""

    TERMS: ClassVar[tuple[RequirementTerm, ...]] = TERMS

    @staticmethod
    def match_terms(text: str) -> tuple[RequirementTerm, ...]:
        """All requirement terms mentioned in `text`, most specific first.

        The generic `smart_hub` term is only returned when no specific hub/gateway matched.
        """
        matched = [term for term in TERMS if term.pattern.search(text)]
        specific_hub = any(
            t.kind in (RequirementKind.HUB, RequirementKind.GATEWAY) and t.canonical != "smart_hub" for t in matched
        )
        if specific_hub:
            matched = [term for term in matched if term.canonical != "smart_hub"]
        return tuple(matched)

    @staticmethod
    def lookup(item: str) -> RequirementTerm | None:
        """Best canonical term for a free-text requirement item."""
        matched = RequirementVocabulary.match_terms(item)
        return matched[0] if matched else None

    @staticmethod
    def term_by_canonical(canonical: str | None) -> RequirementTerm | None:
        return _BY_CANONICAL.get(canonical) if canonical else None


_BY_CANONICAL = {term.canonical: term for term in TERMS}
