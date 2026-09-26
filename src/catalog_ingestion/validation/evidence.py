"""Evidence verification: an LLM claim is only accepted when its quote is found in the source
it cites."""

import re
from dataclasses import dataclass

from catalog_ingestion.domain.enrichment import WebPage
from catalog_ingestion.domain.enums import FactSource
from catalog_ingestion.domain.product import NormalizedProduct

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
_ELLIPSIS = re.compile(r"\.\.\.|…")
_EDGE_PUNCTUATION = " \"'.,;:!?()[]"
MIN_QUOTE_LENGTH = 3


def normalize_text(text: str) -> str:
    return _WHITESPACE.sub(" ", text.translate(_TRANSLATION)).strip().casefold()


def catalog_text(product: NormalizedProduct) -> str:
    """All catalog strings the LLM saw, in the same `Key: Value` form used in the prompt."""
    parts = [
        product.title,
        product.subtitle,
        *product.variants,
        *product.description.highlights,
        product.description.text,
    ]
    parts.extend(product.attributes.badges)
    parts.extend(f"{entry.key}: {entry.value}" for entry in product.attributes.entries)
    parts.extend(product.attributes.unparsed_lines)
    if product.category_slug:
        parts.append(product.category_slug)
    return "\n".join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class SourceTexts:
    catalog: str
    web: str
    web_url: str | None

    @classmethod
    def build(cls, product: NormalizedProduct, web_page: WebPage | None) -> "SourceTexts":
        web_ok = web_page is not None and web_page.ok
        return cls(
            catalog=normalize_text(catalog_text(product)),
            web=normalize_text(web_page.text) if web_ok and web_page else "",
            web_url=web_page.url if web_ok and web_page else None,
        )

    def text_for(self, source: FactSource) -> str:
        return self.web if source is FactSource.WEB else self.catalog

    def locate(self, quote: str, cited: FactSource) -> FactSource | None:
        """Source that contains `quote`: the cited one first, then the other one."""
        for source in (cited, FactSource.WEB if cited is FactSource.CATALOG else FactSource.CATALOG):
            if quote_found(quote, self.text_for(source)):
                return source
        return None


def quote_found(quote: str, normalized_source: str) -> bool:
    if not normalized_source:
        return False
    fragments = [normalize_text(fragment).strip(_EDGE_PUNCTUATION) for fragment in _ELLIPSIS.split(quote)]
    fragments = [fragment for fragment in fragments if fragment]
    if not fragments or sum(len(fragment) for fragment in fragments) < MIN_QUOTE_LENGTH:
        return False
    return all(fragment in normalized_source for fragment in fragments)


def mentions_any(text: str, forms: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(form) in normalized for form in forms)
