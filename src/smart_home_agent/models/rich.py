"""Presentation tags the agent may put in an answer, and the catalog data the UI renders them with.

Five self-closing tags are recognized, with 8-digit catalog ids only:
    <item id="ID"/>                  inline product reference
    <items ids="ID,ID"/>             product list
    <compare ids="ID,ID"/>           side-by-side comparison (2-4 products)
    <compatibility id="ID"/>         compatibility of one product
    <upgrade from="ID" to="ID"/>     higher-value alternative (only the recommender's upsell)

Anything else that looks like markup stays plain text, and tags inside fenced code blocks are not parsed.
`strip_invalid_tags` removes malformed tags from the answer before it is shown or kept in the history.
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
# Anything that looks like one of the tags (opening, closing, self-closing, or cut off at the line end).
_TAG_LIKE = re.compile(r"</?\s*(?:items?|compare|compatibility|upgrade)\b[^<>\n]*(?:>|$)", re.IGNORECASE | re.MULTILINE)
_REMOVED = "\x00"  # marks a removed tag, so a line that held only tags goes away entirely
_COMPARE_SIZES = range(2, 5)  # services.comparison.MIN_PRODUCTS..MAX_PRODUCTS


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


def _renderable(tag: str, upsell: tuple[str, str] | None) -> bool:
    if _ITEM.fullmatch(tag):
        return True
    match = _BLOCK.fullmatch(tag)
    if match is None:
        return False
    match _block(match):
        case CompareBlock(ids):
            return len(ids) in _COMPARE_SIZES
        case UpgradeBlock(from_id, to_id):
            return (from_id, to_id) == upsell
    return True


def _tidy(text: str) -> str:
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)  # keeps list indentation
    text = re.sub(r"[ \t]+(?=[.,;:!?)])", "", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", text)


def strip_invalid_tags(text: str, upsell: tuple[str, str] | None = None) -> str:
    """Removes tag markup that would never be rendered: a tag with a non-catalog id (`<item id="hue_bridge"/>`),
    wrong attributes, an opening/closing pair (the enclosed text stays), a <compare> of fewer than two or more
    than four products, or an <upgrade> that is not `upsell` (base id, upsell id). Valid tags and code fences
    stay unchanged. Whether an id exists in the catalog is the output check's job."""
    out: list[str] = []
    for part, is_code in _outside_fences(text):
        if is_code:
            out.append(part)
            continue
        marked = _TAG_LIKE.sub(lambda m: m[0] if _renderable(m[0], upsell) else _REMOVED, part)
        if marked == part:
            out.append(part)
            continue
        marked = re.sub(rf"^[ \t]*{_REMOVED}(?:[ \t]*{_REMOVED})*[ \t]*(?:\n|$)", "", marked, flags=re.MULTILINE)
        out.append(_tidy(marked.replace(_REMOVED, "")))
    return "".join(out).strip()


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
    "<item/> (Title)", "**Title** <item/>"): the tag already renders the name, so the echo would show it twice.
    An echo with more words keeps them: "<item/> (Title in anthracite)" -> "<item/> (in anthracite)"."""
    for pid, title in titles.items():
        if not title.strip():
            continue
        bare = rf"(?:\*\*)?{re.escape(title.strip())}(?:\*\*)?"
        name = rf"(?:\({bare}\)|{bare})"  # also "<item/> (Title)", the model's habit of repeating the name
        tag = rf'<item\s+id="{pid}"\s*/>'
        text = re.sub(rf"({tag})[ \t]*[:,-]?[ \t]*{name}", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(rf"({tag})[ \t]*\({bare}[ \t]+(?=[^)\s])", r"\1 (", text, flags=re.IGNORECASE)
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


def to_plain(text: str, titles: Mapping[str, str], names: Mapping[str, str] | None = None) -> str:
    """Text-only rendering (terminal chat, or when no data could be resolved): never shows raw tags.
    Like the web interface, an inline <item/> shows the catalog title (the model names the version in its
    own words) and an <items> list shows `names` (title plus version label, the cards' subtitle line)."""

    def title(pid: str) -> str:
        return titles.get(pid) or pid

    def name(pid: str) -> str:
        return (names or {}).get(pid) or title(pid)

    parts = []
    for segment in parse(text):
        match segment:
            case TextSegment(body):
                parts.append(replace_items(strip_echoed_titles(body, titles), title))
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

    def names(self) -> dict[str, str]:
        """Display names: the title plus the version label, so two versions of one product read differently."""
        return {pid: p.name for pid, p in self.products.items()}
