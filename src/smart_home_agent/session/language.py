"""English/German detection for the latest user message, via lingua.

The catalog text is German, which pulls the model towards German answers. A per-turn hint makes
the reply language follow the user instead. Returns None when the message is too short or the
detector is unsure; the model then decides on its own.
"""

import re
from functools import cache

from lingua import Language, LanguageDetector, LanguageDetectorBuilder

_WORDS = re.compile(r"[^\W\d_]+")
_SENTENCES = re.compile(r"(?<=[.!?\n])\s+")
# German compounds that share a tail ("Fenster- und Türkontakt") keep their "und" out of the evidence.
_COMPOUND_HEAD = re.compile(r"\b\w+-\s+(?:und|oder)\s+")
# A capitalized word inside a sentence is a name (product, brand, person) or a German noun; "I" is kept.
_CAPITALIZED = re.compile(r"\b(?!I\b)[A-ZÄÖÜ][\w-]*")
_CODES = {Language.ENGLISH: "en", Language.GERMAN: "de"}
MIN_WORDS = 2
# lingua is cautious on short English ("I need a Matter smart plug." scores 0.61), so this only rejects near-ties.
MIN_CONFIDENCE = 0.55


@cache
def _detector() -> LanguageDetector:
    return LanguageDetectorBuilder.from_languages(*_CODES).build()


def _without_names(text: str) -> str:
    """Drops capitalized words after the first of each sentence, so an English question about a German product
    ("Is the Heizkörperthermostat any good?") or a name ("I am Jürgen") is judged by its own words. German keeps
    enough lowercase function words to stay German."""
    sentences = []
    for sentence in _SENTENCES.split(_COMPOUND_HEAD.sub("", text.strip())):
        first, _, rest = sentence.partition(" ")
        sentences.append(f"{first} {_CAPITALIZED.sub('', rest)}")
    return " ".join(sentences)


def detect_language(text: str) -> str | None:
    text = _without_names(text)
    if len(_WORDS.findall(text)) < MIN_WORDS:
        return None
    best = _detector().compute_language_confidence_values(text)[0]
    return _CODES[best.language] if best.value >= MIN_CONFIDENCE else None
