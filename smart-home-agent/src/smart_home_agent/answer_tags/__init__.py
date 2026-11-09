"""Presentation tags the agent may put in an answer: parsing, cleanup and text rendering.

Five self-closing tags are recognized, with 8-digit catalog ids only:
    <item id="ID"/>                  inline product reference
    <items ids="ID,ID"/>             product list
    <compare ids="ID,ID"/>           side-by-side comparison (2-4 products)
    <compatibility id="ID"/>         compatibility of one product
    <upgrade from="ID" to="ID"/>     higher-value alternative (only the recommender's upsell)

Anything else that looks like markup stays plain text, and tags inside fenced code blocks are not parsed.
A tag only says what to show: every value comes from `models.RichContent`, which is resolved from PostgreSQL.

Flow of one answer:
1. `TagSanitizer` (after_model_callback) removes malformed tags before the answer is shown or kept in the history.
2. `TagParser` splits the answer into `TextSegment`s and blocks (`ItemsBlock`, `CompareBlock`, `CompatibilityBlock`,
   `UpgradeBlock`) and lists the ids they reference (rich content resolution, output check, UI).
3. `ProseRenderer` renders the inline <item/> tags of a text segment (web UI); `PlainTextRenderer` renders the
   whole answer as text without tags (terminal chat, or when no catalog data could be resolved).
"""

from smart_home_agent.answer_tags.plain_text_renderer import PlainTextRenderer
from smart_home_agent.answer_tags.prose_renderer import ProseRenderer
from smart_home_agent.answer_tags.segments import (
    Block,
    CompareBlock,
    CompatibilityBlock,
    ItemsBlock,
    Segment,
    TextSegment,
    UpgradeBlock,
)
from smart_home_agent.answer_tags.tag_parser import TagParser
from smart_home_agent.answer_tags.tag_sanitizer import TagSanitizer

__all__ = [
    "Block",
    "CompareBlock",
    "CompatibilityBlock",
    "ItemsBlock",
    "PlainTextRenderer",
    "ProseRenderer",
    "Segment",
    "TagParser",
    "TagSanitizer",
    "TextSegment",
    "UpgradeBlock",
]
