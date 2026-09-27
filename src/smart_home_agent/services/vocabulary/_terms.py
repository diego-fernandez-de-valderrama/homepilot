"""Compatibility terms (ecosystems, voice assistants, protocols, mobile OS): free text -> canonical term."""

import re

from catalog_ingestion.vocabulary import compatibility as compatibility_vocabulary

from smart_home_agent.services.vocabulary._aliases import AMBIGUOUS_TERMS, EXTRA_TERM_ALIASES, TERM_SUFFIXES, key
from smart_home_agent.services.vocabulary.resolved_term import ResolvedTerm
from smart_home_agent.services.vocabulary.term_resolution_error import TermResolutionError

_TERMS_BY_LABEL: dict[str, str] = {key(t.label): t.canonical for t in compatibility_vocabulary.TERMS}


def term(canonical: str) -> ResolvedTerm:
    found = compatibility_vocabulary.term_by_canonical(canonical)
    if found is None:
        raise TermResolutionError("compatibility term", canonical)
    return ResolvedTerm(found.canonical, found.dimension, found.label)


def label(canonical: str) -> str:
    found = compatibility_vocabulary.term_by_canonical(canonical)
    return found.label if found else canonical


def resolve_term(value: str) -> ResolvedTerm:
    """Free text ("HomeKit", "Google Home", "matter-kompatibel", "zigbee") -> canonical term."""
    normalized = TERM_SUFFIXES.sub("", key(value)).strip()
    if compatibility_vocabulary.term_by_canonical(normalized):
        return term(normalized)
    if normalized in _TERMS_BY_LABEL:  # the labels the tools return ("Apple Home (HomeKit)") must resolve back
        return term(_TERMS_BY_LABEL[normalized])
    if normalized in EXTRA_TERM_ALIASES:
        return term(EXTRA_TERM_ALIASES[normalized])
    options = AMBIGUOUS_TERMS.get(normalized)
    if options and len(options) == 1:
        return term(options[0])
    if options:
        raise TermResolutionError("compatibility term", value, [label(o) for o in options])
    found = compatibility_vocabulary.lookup(normalized)
    if found is None:
        raise TermResolutionError("compatibility term", value)
    return ResolvedTerm(found.canonical, found.dimension, found.label)


def mentions_term(canonical: str, normalized_text: str) -> bool:
    """True when the text names the compatibility term (an ingestion surface form or a conversational alias)."""
    found = compatibility_vocabulary.term_by_canonical(canonical)
    forms = set(compatibility_vocabulary.surface_forms(canonical)) if found else set()
    forms |= {alias for alias, target in EXTRA_TERM_ALIASES.items() if target == canonical}
    return any(re.search(rf"(?<!\w){re.escape(form)}(?!\w)", normalized_text) for form in forms if form)
