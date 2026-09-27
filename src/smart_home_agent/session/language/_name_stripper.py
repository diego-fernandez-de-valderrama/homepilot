import re

_SENTENCES = re.compile(r"(?<=[.!?\n])\s+")
# German compounds that share a tail ("Fenster- und Türkontakt") keep their "und" out of the evidence.
_COMPOUND_HEAD = re.compile(r"\b\w+-\s+(?:und|oder)\s+")
# A capitalized word inside a sentence is a name (product, brand, person) or a German noun; "I" is kept.
_CAPITALIZED = re.compile(r"\b(?!I\b)[A-ZÄÖÜ][\w-]*")


class NameStripper:
    """Drops capitalized words after the first of each sentence, so an English question about a German product
    ("Is the Heizkörperthermostat any good?") or a name ("I am Jürgen") is judged by its own words. German keeps
    enough lowercase function words to stay German."""

    @staticmethod
    def strip(text: str) -> str:
        sentences = []
        for sentence in _SENTENCES.split(_COMPOUND_HEAD.sub("", text.strip())):
            first, _, rest = sentence.partition(" ")
            sentences.append(f"{first} {_CAPITALIZED.sub('', rest)}")
        return " ".join(sentences)
