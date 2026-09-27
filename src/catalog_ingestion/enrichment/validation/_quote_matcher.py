import re

from catalog_ingestion.core import TextNormalizer


class QuoteMatcher:
    """Finds an evidence quote in normalized source text. "..." inside a quote separates fragments that
    must all be found, in order for `locate`."""

    MIN_QUOTE_LENGTH = 3
    _ELLIPSIS = re.compile(r"\.\.\.|…")
    _EDGE_PUNCTUATION = " \"'.,;:!?()[]"
    _SENTENCE_END = re.compile(r"\n|[.!?;](?=\s)")

    @staticmethod
    def found(quote: str, normalized_source: str) -> bool:
        if not normalized_source:
            return False
        fragments = QuoteMatcher.fragments(quote)
        if not fragments or sum(len(fragment) for fragment in fragments) < QuoteMatcher.MIN_QUOTE_LENGTH:
            return False
        return all(fragment in normalized_source for fragment in fragments)

    @staticmethod
    def fragments(quote: str) -> list[str]:
        fragments = [
            TextNormalizer.normalize(fragment).strip(QuoteMatcher._EDGE_PUNCTUATION)
            for fragment in QuoteMatcher._ELLIPSIS.split(quote)
        ]
        return [fragment for fragment in fragments if fragment]

    @staticmethod
    def locate(quote: str, lines_text: str) -> tuple[int, int] | None:
        """Start and end of the quote in text normalized with `TextNormalizer.normalize_lines`."""
        fragments = QuoteMatcher.fragments(quote)
        if not fragments:
            return None
        start = lines_text.find(fragments[0])
        if start < 0:
            return None
        end_fragment = lines_text.find(fragments[-1], start)
        return start, (end_fragment if end_fragment >= 0 else start) + len(fragments[-1])

    @staticmethod
    def sentence(quote: str, lines_text: str) -> str | None:
        """The sentence(s) of the source (normalized with `normalize_lines`) that contain the quote."""
        span = QuoteMatcher.locate(quote, lines_text)
        if span is None:
            return None
        start, end = span
        before = [match.end() for match in QuoteMatcher._SENTENCE_END.finditer(lines_text, 0, start)]
        after = QuoteMatcher._SENTENCE_END.search(lines_text, end)
        return lines_text[before[-1] if before else 0 : after.start() if after else len(lines_text)]
