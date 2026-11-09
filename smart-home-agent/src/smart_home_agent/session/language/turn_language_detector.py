import re
from functools import cache

from lingua import Language, LanguageDetector, LanguageDetectorBuilder

from smart_home_agent.session.language._name_stripper import NameStripper

_WORDS = re.compile(r"[^\W\d_]+")
_CODES = {Language.ENGLISH: "en", Language.GERMAN: "de"}


class TurnLanguageDetector:
    """English/German detection for the latest user message, via lingua.

    The catalog text is German, which pulls the model towards German answers. A per-turn hint makes the reply
    language follow the user instead. `detect` returns None when the message is too short or the detector is unsure;
    the model then decides on its own.
    """

    MIN_WORDS = 2
    # lingua is cautious on short English ("I need a Matter smart plug." scores 0.61), so this only rejects near-ties.
    MIN_CONFIDENCE = 0.55

    @staticmethod
    def detect(text: str) -> str | None:
        text = NameStripper.strip(text)
        if len(_WORDS.findall(text)) < TurnLanguageDetector.MIN_WORDS:
            return None
        best = TurnLanguageDetector._detector().compute_language_confidence_values(text)[0]
        return _CODES[best.language] if best.value >= TurnLanguageDetector.MIN_CONFIDENCE else None

    @staticmethod
    @cache
    def _detector() -> LanguageDetector:
        return LanguageDetectorBuilder.from_languages(*_CODES).build()
