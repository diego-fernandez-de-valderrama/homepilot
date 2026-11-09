"""The pieces of a parsed answer: text (with inline <item/> tags) and the block tags between it."""

from smart_home_agent.answer_tags.segments.compare_block import CompareBlock
from smart_home_agent.answer_tags.segments.compatibility_block import CompatibilityBlock
from smart_home_agent.answer_tags.segments.items_block import ItemsBlock
from smart_home_agent.answer_tags.segments.text_segment import TextSegment
from smart_home_agent.answer_tags.segments.upgrade_block import UpgradeBlock

type Block = ItemsBlock | CompareBlock | CompatibilityBlock | UpgradeBlock
type Segment = TextSegment | Block

__all__ = ["Block", "CompareBlock", "CompatibilityBlock", "ItemsBlock", "Segment", "TextSegment", "UpgradeBlock"]
