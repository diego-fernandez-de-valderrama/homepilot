"""Presentation tags the agent may put in an answer, and the catalog data the UI renders them with.

Five self-closing tags are recognized, with 8-digit catalog ids only:
    <item id="ID"/>                  inline product reference
    <items ids="ID,ID"/>             product list
    <compare ids="ID,ID"/>           side-by-side comparison (2-4 products)
    <compatibility id="ID"/>         compatibility of one product
    <upgrade from="ID" to="ID"/>     higher-value alternative (only the recommender's upsell)

Anything else that looks like markup stays plain text, and tags inside fenced code blocks are not parsed.
A tag only says what to show: every value comes from `RichContent`, which is resolved from PostgreSQL.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from pydantic import BaseModel, Field

from smart_home_agent.models.comparison import ComparisonResult
from smart_home_agent.models.compatibility import CompatibilityResult
from smart_home_agent.models.product import Product
from smart_home_agent.models.recommendation import UpsellSuggestion

_ID = r"\d{8}"
_IDS = rf"{_ID}(?:\s*,\s*{_ID})*"
_ITEM = re.compile(rf'<item\s+id="({_ID})"\s*/>')
_BLOCK = re.compile(
    rf'<(?P<list>items|compare)\s+ids="(?P<ids>{_IDS})"\s*/>'
    rf'|<compatibility\s+id="(?P<compat>{_ID})"\s*/>'
    rf'|<upgrade\s+from="(?P<from>{_ID})"\s+to="(?P<to>{_ID})"\s*/>'
)
_FENCE = re.compile(r"(```.*?(?:```|\Z))", re.DOTALL)  # capturing: re.split keeps the fences


@dataclass(frozen=True, slots=True)
class TextSegment:
    text: str  # markdown, may contain inline <item/> tags


@dataclass(frozen=True, slots=True)
class ItemsBlock:
    ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompareBlock:
    ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompatibilityBlock:
    product_id: str


@dataclass(frozen=True, slots=True)
class UpgradeBlock:
    from_id: str
    to_id: str


type Block = ItemsBlock | CompareBlock | CompatibilityBlock | UpgradeBlock
type Segment = TextSegment | Block


def _split_ids(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(part.strip() for part in value.split(",")))


def _block(match: re.Match[str]) -> Block:
    if match["list"] == "items":
        return ItemsBlock(_split_ids(match["ids"]))
    if match["list"] == "compare":
        return CompareBlock(_split_ids(match["ids"]))
    if match["compat"]:
        return CompatibilityBlock(match["compat"])
    return UpgradeBlock(match["from"], match["to"])


def _outside_fences(text: str) -> list[tuple[str, bool]]:
    """(part, is_code) pairs in order."""
    return [(part, i % 2 == 1) for i, part in enumerate(_FENCE.split(text)) if part]


def parse(text: str) -> list[Segment]:
    segments: list[Segment] = []
    buffer: list[str] = []

    def flush() -> None:
        joined = "".join(buffer).strip("\n")
        if joined.strip():
            segments.append(TextSegment(joined))
        buffer.clear()

    for part, is_code in _outside_fences(text):
        if is_code:
            buffer.append(part)
            continue
        last = 0
        for match in _BLOCK.finditer(part):
            buffer.append(part[last : match.start()])
            flush()
            segments.append(_block(match))
            last = match.end()
        buffer.append(part[last:])
    flush()
    return segments


def render_prose(text: str, render_text: Callable[[str], str], render_item: Callable[[str], str]) -> str:
    """Code fences stay unchanged; elsewhere every run of text goes through `render_text` and every inline
    <item/> through `render_item(product_id)`."""
    out: list[str] = []
    for part, is_code in _outside_fences(text):
        if is_code:
            out.append(part)
            continue
        pieces = _ITEM.split(part)  # the id group is captured: odd positions are product ids
        out += [render_item(piece) if i % 2 else render_text(piece) for i, piece in enumerate(pieces)]
    return "".join(out)


def replace_items(text: str, render: Callable[[str], str]) -> str:
    """Replaces every inline <item/> outside code fences by `render(product_id)`."""
    return render_prose(text, lambda piece: piece, render)


def strip_echoed_titles(text: str, titles: Mapping[str, str]) -> str:
    """Removes a product title the model wrote right next to that product's own <item/> tag ("<item/> Title",
    "**Title** <item/>"): the tag already renders the name, so the echo would show it twice."""
    for pid, title in titles.items():
        if not title.strip():
            continue
        name = rf"(?:\*\*)?{re.escape(title.strip())}(?:\*\*)?"
        tag = rf'<item\s+id="{pid}"\s*/>'
        text = re.sub(rf"({tag})[ \t]*[:,-]?[ \t]*{name}", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(rf"{name}[ \t]*[:,-]?[ \t]*\(?({tag})\)?", r"\1", text, flags=re.IGNORECASE)
    return text


def inline_ids(text: str) -> list[str]:
    return list(
        dict.fromkeys(pid for part, is_code in _outside_fences(text) if not is_code for pid in _ITEM.findall(part))
    )


def referenced_ids(segments: list[Segment]) -> list[str]:
    ids: list[str] = []
    for segment in segments:
        match segment:
            case TextSegment(text):
                ids += inline_ids(text)
            case ItemsBlock(block_ids) | CompareBlock(block_ids):
                ids += block_ids
            case CompatibilityBlock(product_id):
                ids.append(product_id)
            case UpgradeBlock(from_id, to_id):
                ids += [from_id, to_id]
    return list(dict.fromkeys(ids))


def block_ids(segments: list[Segment]) -> set[str]:
    """Products displayed by a block component (an inline <item/> for them would repeat the block)."""
    return set(referenced_ids([s for s in segments if not isinstance(s, TextSegment)]))


def to_plain(text: str, titles: Mapping[str, str]) -> str:
    """Text-only rendering (terminal chat, or when no data could be resolved): never shows raw tags."""

    def name(pid: str) -> str:
        return titles.get(pid) or pid

    parts = []
    for segment in parse(text):
        match segment:
            case TextSegment(body):
                parts.append(replace_items(strip_echoed_titles(body, titles), name))
            case ItemsBlock(ids):
                parts.append("\n".join(f"- {name(pid)}" for pid in ids))
    return "\n\n".join(parts)


def upgrade_key(from_id: str, to_id: str) -> str:
    return f"{from_id}>{to_id}"


def compare_key(ids: tuple[str, ...]) -> str:
    return ",".join(ids)


class ProductCompatibility(BaseModel):
    result: CompatibilityResult
    against_setup: bool  # True: checked against the customer's stated setup; False: the product's own facts


class RichContent(BaseModel):
    """Catalog data for the tags of one answer, keyed like the tags (never taken from the model's text)."""

    products: dict[str, Product] = Field(default_factory=dict)
    compatibility: dict[str, ProductCompatibility] = Field(default_factory=dict)
    comparisons: dict[str, ComparisonResult] = Field(default_factory=dict)  # compare_key(ids) -> result
    upgrades: dict[str, UpsellSuggestion] = Field(default_factory=dict)  # upgrade_key(from, to) -> upsell

    def titles(self) -> dict[str, str]:
        return {pid: p.title for pid, p in self.products.items()}
