"""Lightweight English/German detection for the latest user message.

The catalog text is German, which pulls the model towards German answers. A per-turn hint makes
the reply language follow the user instead. Returns None when the message is too short or mixed;
the model then decides on its own.
"""

import re

_WORDS = re.compile(r"[a-zäöüß]+")
_GERMAN = frozenset(
    [
        "ich",
        "du",
        "sie",
        "wir",
        "und",
        "oder",
        "aber",
        "nicht",
        "kein",
        "keine",
        "mit",
        "für",
        "ein",
        "eine",
        "einen",
        "einem",
        "der",
        "die",
        "das",
        "den",
        "dem",
        "ist",
        "sind",
        "habe",
        "hast",
        "hat",
        "suche",
        "brauche",
        "möchte",
        "welche",
        "welcher",
        "welches",
        "wie",
        "was",
        "wo",
        "warum",
        "kann",
        "können",
        "soll",
        "auch",
        "noch",
        "mein",
        "meine",
        "meinen",
        "bis",
        "unter",
        "über",
        "zu",
        "von",
        "bitte",
        "danke",
        "gibt",
        "es",
        "funktioniert",
        "kompatibel",
        "vergleiche",
        "mir",
        "mich",
        "dein",
        "deine",
        "deinen",
        "zeige",
        "zeig",
        "gib",
    ]
)
_ENGLISH = frozenset(
    [
        "i",
        "you",
        "we",
        "and",
        "or",
        "but",
        "not",
        "no",
        "with",
        "for",
        "a",
        "an",
        "the",
        "is",
        "are",
        "have",
        "has",
        "need",
        "want",
        "looking",
        "which",
        "what",
        "where",
        "why",
        "how",
        "can",
        "could",
        "should",
        "also",
        "my",
        "me",
        "to",
        "from",
        "under",
        "up",
        "please",
        "thanks",
        "there",
        "does",
        "do",
        "work",
        "works",
        "compatible",
        "compare",
        "something",
        "anything",
        "your",
        "show",
        "give",
        "tell",
    ]
)
MIN_EVIDENCE = 2


def detect_language(text: str) -> str | None:
    words = _WORDS.findall(text.casefold())
    german = sum(w in _GERMAN for w in words) + 2 * sum(ch in "äöüß" for ch in text.casefold())
    english = sum(w in _ENGLISH for w in words)
    if max(german, english) < MIN_EVIDENCE or german == english:
        return None
    return "de" if german > english else "en"
