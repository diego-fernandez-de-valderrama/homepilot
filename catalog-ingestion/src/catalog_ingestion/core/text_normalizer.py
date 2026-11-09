import re
import unicodedata

from anyascii import anyascii


class TextNormalizer:
    """The one normalization every comparison with source text or a customer's words goes through (catalog
    claim validation and the agent's customer memory).

    Non-ASCII punctuation and spaces (typographic quotes, accents used as apostrophes, dashes, primes,
    non-breaking spaces) are transliterated to ASCII by anyascii before matching. Letters and symbols are kept
    (umlauts, "ß", "€", "°"): the catalog is German, and transliterating them would change what matches.
    """

    _NON_ASCII = re.compile(r"[^\x00-\x7f]")
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
        return TextNormalizer._WHITESPACE.sub(" ", TextNormalizer._NON_ASCII.sub(TextNormalizer._to_ascii, text))

    @staticmethod
    def _to_ascii(match: re.Match[str]) -> str:
        char = match[0]
        category = unicodedata.category(char)
        return anyascii(char) if category[0] == "P" or category in ("Zs", "Sk") else char
