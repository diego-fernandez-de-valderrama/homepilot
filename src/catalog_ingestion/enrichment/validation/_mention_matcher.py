import re

from catalog_ingestion.core import TextNormalizer
from catalog_ingestion.enrichment.validation._quote_matcher import QuoteMatcher


class MentionMatcher:
    """Whether a text names a term (whole words) and whether that mention is negated in its own clause."""

    NEGATION_WORDS = 3
    # "matter" is also the German adjective (matte finish): a lowercase "matter" followed by a capitalized word
    # ("matter Lack", "matter Oberfläche") is that adjective. Titles use "... 1100 matter" and "matterkompatibel".
    _MATTER = re.compile(
        r"(?<!\w)(?:Matter|MATTER)(?!\w)|(?<!\w)matter(?:kompatib|fähig|zertifi)|(?<!\w)matter(?!\w)(?!\s+[A-ZÄÖÜ])"
    )
    _MENTION_WORD = re.compile(r"[\wäöüß+]{3,}", re.IGNORECASE)
    _CLAUSE_BOUNDARY = re.compile(r"[\n,;:()\[\]]|[.!?](?=\s|$)|\s[-–]\s")
    # Negation words (DE/EN). "kein" also covers keine/keinen/keiner; "not" never as German "Not-" (emergency).
    _NEGATION = re.compile(r"^(kein\w*|ohne|nicht|weder|no|not|non|without|never|nie)$")
    _NEGATION_AFTER = re.compile(r"^(nicht|not)$")
    # "(nicht enthalten)", "nicht im Lieferumfang enthalten", "not included" say what is in the box, not
    # whether something is needed or compatible.
    _NOT_INCLUDED = re.compile(
        r"nicht (?:im lieferumfang )?(?:enthalten|inbegriffen)|nicht im lieferumfang|not included"
    )
    _WORD_TOKEN = re.compile(r"[\w+-]+")

    @staticmethod
    def forms_pattern(forms: tuple[str, ...]) -> re.Pattern[str]:
        """One whole-word pattern over normalized text for several surface forms."""
        normalize = TextNormalizer.normalize
        keys = sorted({normalize(form) for form in forms if normalize(form)}, key=len, reverse=True)
        return re.compile(rf"(?<!\w)(?:{'|'.join(map(re.escape, keys))})(?!\w)" if keys else r"(?!x)x")

    @staticmethod
    def words_pattern(item: str) -> re.Pattern[str] | None:
        """Mention of a free-text item by any of its words (3+ letters, so "Hub" counts)."""
        words = sorted({word.casefold() for word in MentionMatcher._MENTION_WORD.findall(item)}, key=len, reverse=True)
        return re.compile(rf"(?<!\w)(?:{'|'.join(map(re.escape, words))})") if words else None

    @staticmethod
    def mentions_any(text: str, forms: tuple[str, ...]) -> bool:
        """True when `text` names one of `forms` as a whole word ("lan" does not match inside "WLAN")."""
        normalized = TextNormalizer.normalize(text)
        folded_raw = TextNormalizer.fold(text)
        for form in forms:
            key = TextNormalizer.normalize(form)
            if not key:
                continue
            if key == "matter":
                if MentionMatcher._MATTER.search(folded_raw):
                    return True
            elif re.compile(rf"(?<!\w){re.escape(key)}(?!\w)").search(normalized):
                return True
        return False

    @staticmethod
    def negated(
        mention: re.Pattern[str], quote: str, lines_text: str, max_words_before: int | None = NEGATION_WORDS
    ) -> bool:
        """True when a mention of the claimed term is negated in its own clause: a negation word up to
        NEGATION_WORDS words before it ("ohne Gateway", "Kein HUB erforderlich", "nicht kompatibel mit Apple
        HomeKit", "keine zusätzliche Bridge") or "nicht"/"not" right after it ("Hub nicht erforderlich").
        A negation elsewhere in the sentence ("..., wodurch kein weiterer Hub nötig ist") does not count.
        With `max_words_before=None` any negation earlier in the clause counts ("Nicht mehr kompatibel mit
        der Zentrale CCU2")."""
        boundary = MentionMatcher._CLAUSE_BOUNDARY
        span = QuoteMatcher.locate(quote, lines_text)
        if span is None:
            region = TextNormalizer.normalize(quote)
        else:
            start, end = span
            before = [match.end() for match in boundary.finditer(lines_text, 0, start)]
            after = boundary.search(lines_text, end)
            region = lines_text[before[-1] if before else 0 : after.start() if after else len(lines_text)]
        region = MentionMatcher._NOT_INCLUDED.sub(" ", region)
        for clause in boundary.split(region):
            for match in mention.finditer(clause):
                words_before = MentionMatcher._WORD_TOKEN.findall(clause[: match.start()])
                if max_words_before is not None:
                    words_before = words_before[-max_words_before:]
                words_after = MentionMatcher._WORD_TOKEN.findall(clause[match.end() :])[: MentionMatcher.NEGATION_WORDS]
                if any(MentionMatcher._NEGATION.match(word) for word in words_before):
                    return True
                if any(MentionMatcher._NEGATION_AFTER.match(word) for word in words_after):
                    return True
        return False
