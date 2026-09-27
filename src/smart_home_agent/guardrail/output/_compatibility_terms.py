"""Finds canonical compatibility terms (ecosystems, voice assistants, protocols, ...) in a sentence."""

import re

from catalog_ingestion.vocabulary import compatibility as compatibility_vocabulary


def _surface_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Word-boundary patterns for every surface form of every canonical term (longest first)."""
    forms: dict[str, str] = {}
    for term in compatibility_vocabulary.TERMS:
        for form in compatibility_vocabulary.surface_forms(term.canonical):
            if len(form) >= 3:  # "lan", "hue" and longer; shorter forms are too ambiguous in prose
                forms.setdefault(form, term.canonical)
    ordered = sorted(forms, key=len, reverse=True)
    return [(re.compile(rf"(?<![\w-]){re.escape(form)}(?![\w-])", re.IGNORECASE), forms[form]) for form in ordered]


_TERM_PATTERNS = _surface_patterns()
# Terms whose everyday meaning collides with prose ("no matter what", "Funk" in German compounds).
_AMBIGUOUS_WORDS = frozenset({"matter", "funk", "lan", "hue", "nest"})


def terms_in(sentence: str) -> set[str]:
    found: set[str] = set()
    for pattern, canonical in _TERM_PATTERNS:
        for match in pattern.finditer(sentence):
            word = match.group(0)
            if word.casefold() in _AMBIGUOUS_WORDS and not word[0].isupper():
                continue  # lowercase "matter"/"hue" in running text is not the product term
            found.add(canonical)
    return found
