"""Product models used during internal processing."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class RawProduct:
    """One product exactly as found in products.zip (no cleaning applied)."""

    id: str
    title: str
    subtitle: str
    price: str
    variants: tuple[str, ...]
    description: str
    attributes: str
    image: str
    url: str
    original: Mapping[str, Any] = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class Price:
    value: Decimal | None
    currency: str | None
    original_value: Decimal | None = None
    savings: Decimal | None = None
    raw: str = ""


@dataclass(frozen=True, slots=True)
class Description:
    highlights: tuple[str, ...]
    text: str

    @property
    def is_empty(self) -> bool:
        return not self.highlights and not self.text


@dataclass(frozen=True, slots=True)
class SubtitleParts:
    features: tuple[str, ...]
    properties: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class AttributeEntry:
    section: str
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class ParsedAttributes:
    badges: tuple[str, ...]
    entries: tuple[AttributeEntry, ...]
    unparsed_lines: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.entries

    def get(self, key: str) -> str | None:
        """First value for `key`, or None."""
        return next((entry.value for entry in self.entries if entry.key == key), None)

    def get_all(self, key: str) -> tuple[AttributeEntry, ...]:
        return tuple(entry for entry in self.entries if entry.key == key)


@dataclass(frozen=True, slots=True)
class NormalizedProduct:
    id: str
    title: str
    subtitle: str
    subtitle_parts: SubtitleParts
    brand: str | None
    category_slug: str | None
    category: str | None
    price: Price
    variants: tuple[str, ...]
    description: Description
    attributes: ParsedAttributes
    ean: str | None
    is_smart_home: bool | None
    image_url: str | None
    source_url: str | None
