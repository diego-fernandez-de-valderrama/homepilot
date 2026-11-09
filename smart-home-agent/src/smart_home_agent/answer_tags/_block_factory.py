import re

from smart_home_agent.answer_tags.segments import Block, CompareBlock, CompatibilityBlock, ItemsBlock, UpgradeBlock


class BlockFactory:
    """Builds the block for a match of `_patterns.BLOCK`."""

    @staticmethod
    def from_match(match: re.Match[str]) -> Block:
        if match["list"] == "items":
            return ItemsBlock(BlockFactory._split_ids(match["ids"]))
        if match["list"] == "compare":
            return CompareBlock(BlockFactory._split_ids(match["ids"]))
        if match["compat"]:
            return CompatibilityBlock(match["compat"])
        if match["from"]:
            return UpgradeBlock(match["from"], match["to"])
        return UpgradeBlock(match["from_second"], match["to_first"])

    @staticmethod
    def _split_ids(value: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(part.strip() for part in value.split(",")))
