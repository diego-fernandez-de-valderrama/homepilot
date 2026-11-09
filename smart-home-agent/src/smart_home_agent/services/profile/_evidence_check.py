"""The evidence rules: a verbatim quote of the customer's own words, and every value stated by them."""

import re

from catalog_ingestion.core import TextNormalizer

from smart_home_agent.models import FactKind, NewFact
from smart_home_agent.services.profile._fact_builder import OWNED_KINDS
from smart_home_agent.services.profile._text import MAX_EVIDENCE, MIN_EVIDENCE, unquote
from smart_home_agent.services.profile._third_party import about_someone_else, clauses
from smart_home_agent.services.profile.memory_rule_error import MemoryRuleError
from smart_home_agent.services.vocabulary import Vocabulary

_LANGUAGE_WORDS = {
    "en": re.compile(r"\b(english|englisch)\b", re.IGNORECASE),
    "de": re.compile(r"\b(german|deutsch)\b", re.IGNORECASE),
}
_WORD = re.compile(r"[^\W_]+")
# Words that never back a value on their own ("my", "the", "mein", ...).
_FILLER = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "my",
        "a",
        "an",
        "of",
        "in",
        "on",
        "to",
        "use",
        "have",
        "own",
        "ich",
        "mein",
        "meine",
        "meinen",
        "einen",
        "eine",
        "ein",
        "der",
        "die",
        "das",
        "und",
        "mit",
        "habe",
        "hab",
        "nutze",
        "benutze",
    ]
)


def check_quote(user_message: str | None, evidence: str) -> str:
    """The quote, when it is a whole-word verbatim part of the message and not about someone else; else raises
    `MemoryRuleError`."""
    quote = unquote(evidence)
    if len(quote) < MIN_EVIDENCE:
        raise MemoryRuleError("evidence is required: quote the customer's own words from their latest message")
    if len(quote) > MAX_EVIDENCE:
        raise MemoryRuleError("evidence is too long: quote only the sentence that states the fact")
    message = TextNormalizer.normalize(user_message or "")
    # Whole words only: a fragment such as "e" inside "use" is not a quote.
    span = re.search(rf"(?<!\w){re.escape(TextNormalizer.normalize(quote))}(?!\w)", message)
    if span is None:
        raise MemoryRuleError(
            "evidence is not a verbatim quote of the customer's latest message: only facts the customer stated "
            "in this message can be remembered (never the cart, a tool result or an assumption)"
        )
    if any(about_someone_else(clause) for clause in clauses(message, *span.span())):
        raise MemoryRuleError(
            "the quote is about someone else (friend, family, gift): facts about other people are never stored"
        )
    return quote


def backed_by(fact: NewFact, text: str) -> bool:
    """The customer's own words state the value (`text`: the quote plus the message's clauses that are not
    about someone else), so the model cannot attach a guess, a cart line or a tool result to a quote."""
    if fact.kind is FactKind.LANGUAGE:
        return bool(_LANGUAGE_WORDS[fact.value].search(text))
    if fact.kind is FactKind.ECOSYSTEM and fact.canonical and Vocabulary.mentions_term(fact.canonical, text):
        return True
    if fact.kind in OWNED_KINDS and fact.canonical and Vocabulary.mentions_requirement(fact.canonical, text):
        return True
    min_length = 4 if fact.kind is FactKind.PREFERENCE else 2
    words = [
        w for w in _WORD.findall(TextNormalizer.normalize(fact.label)) if len(w) >= min_length and w not in _FILLER
    ]
    # Preferences may be inflected ("günstige" for "günstig"): a shared stem of 5 letters counts.
    return any(re.search(rf"(?<!\w){re.escape(w[:5] if fact.kind is FactKind.PREFERENCE else w)}", text) for w in words)
