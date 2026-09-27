from smart_home_agent.answer_tags import _patterns
from smart_home_agent.answer_tags._block_factory import BlockFactory
from smart_home_agent.answer_tags._code_fences import CodeFences
from smart_home_agent.answer_tags.segments import (
    CompareBlock,
    CompatibilityBlock,
    ItemsBlock,
    Segment,
    TextSegment,
    UpgradeBlock,
)


class TagParser:
    """Splits an answer into text segments and block tags, and lists the product ids they reference."""

    @staticmethod
    def parse(text: str) -> list[Segment]:
        segments: list[Segment] = []
        buffer: list[str] = []

        def flush() -> None:
            joined = "".join(buffer).strip("\n")
            if joined.strip():
                segments.append(TextSegment(joined))
            buffer.clear()

        for part, is_code in CodeFences.split(text):
            if is_code:
                buffer.append(part)
                continue
            last = 0
            for match in _patterns.BLOCK.finditer(part):
                buffer.append(part[last : match.start()])
                flush()
                segments.append(BlockFactory.from_match(match))
                last = match.end()
            buffer.append(part[last:])
        flush()
        return segments

    @staticmethod
    def inline_ids(text: str) -> list[str]:
        """Ids of the inline <item/> tags outside code fences, in order, without duplicates."""
        return list(
            dict.fromkeys(
                pid for part, is_code in CodeFences.split(text) if not is_code for pid in _patterns.ITEM.findall(part)
            )
        )

    @staticmethod
    def referenced_ids(segments: list[Segment]) -> list[str]:
        ids: list[str] = []
        for segment in segments:
            match segment:
                case TextSegment(text):
                    ids += TagParser.inline_ids(text)
                case ItemsBlock(block_ids) | CompareBlock(block_ids):
                    ids += block_ids
                case CompatibilityBlock(product_id):
                    ids.append(product_id)
                case UpgradeBlock(from_id, to_id):
                    ids += [from_id, to_id]
        return list(dict.fromkeys(ids))

    @staticmethod
    def block_ids(segments: list[Segment]) -> set[str]:
        """Products displayed by a block component (an inline <item/> for them would repeat the block)."""
        return set(TagParser.referenced_ids([s for s in segments if not isinstance(s, TextSegment)]))
