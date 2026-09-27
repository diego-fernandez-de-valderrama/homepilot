import re


class TextNormalizer:
    """The one normalization every comparison with source text goes through."""

    # Typographic quotes, en/em dashes and non-breaking spaces are folded to ASCII before matching.
    _TRANSLATION = str.maketrans(
        {
            "\u201e": '"',
            "\u201c": '"',
            "\u201d": '"',
            "\u201a": "'",
            "\u2018": "'",
            "\u2019": "'",
            "\u2013": "-",
            "\u2014": "-",
            "\u00a0": " ",
        }
    )
    _WHITESPACE = re.compile(r"\s+")

    @staticmethod
    def normalize(text: str) -> str:
        """Folded punctuation, single spaces, casefolded."""
        return TextNormalizer.fold(text).strip().casefold()

    @staticmethod
    def normalize_lines(text: str) -> str:
        """Like `normalize`, but keeps line breaks (attribute lines, paragraphs) as boundaries."""
        return "\n".join(line for line in (TextNormalizer.normalize(line) for line in text.splitlines()) if line)

    @staticmethod
    def fold(text: str) -> str:
        """Folded punctuation and single spaces, case kept."""
        return TextNormalizer._WHITESPACE.sub(" ", text.translate(TextNormalizer._TRANSLATION))
