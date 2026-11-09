import re

from smart_home_agent.answer_tags import _patterns
from smart_home_agent.answer_tags._block_factory import BlockFactory
from smart_home_agent.answer_tags._code_fences import CodeFences
from smart_home_agent.answer_tags.segments import CompareBlock, UpgradeBlock

_REMOVED = "\x00"  # marks a removed tag, so a line that held only tags goes away entirely


class TagSanitizer:
    """Removes tag markup that would never be rendered: a tag with a non-catalog id (`<item id="hue_bridge"/>`),
    wrong attributes, an opening/closing pair (the enclosed text stays), a <compare> of fewer than two or more
    than four products, or an <upgrade> that is not `upsell` (base id, upsell id). Valid tags and code fences
    stay unchanged. Whether an id exists in the catalog is the output check's job."""

    def __init__(self, upsell: tuple[str, str] | None = None) -> None:
        self._upsell = upsell

    def strip_invalid(self, text: str) -> str:
        out: list[str] = []
        for part, is_code in CodeFences.split(text):
            if is_code:
                out.append(part)
                continue
            marked = _patterns.TAG_LIKE.sub(lambda m: m[0] if self._renderable(m[0]) else _REMOVED, part)
            if marked == part:
                out.append(part)
                continue
            marked = re.sub(rf"^[ \t]*{_REMOVED}(?:[ \t]*{_REMOVED})*[ \t]*(?:\n|$)", "", marked, flags=re.MULTILINE)
            out.append(self._tidy(marked.replace(_REMOVED, "")))
        return "".join(out).strip()

    def _renderable(self, tag: str) -> bool:
        if _patterns.ITEM.fullmatch(tag):
            return True
        match = _patterns.BLOCK.fullmatch(tag)
        if match is None:
            return False
        match BlockFactory.from_match(match):
            case CompareBlock(ids):
                return len(ids) in _patterns.COMPARE_SIZES
            case UpgradeBlock(from_id, to_id):
                return (from_id, to_id) == self._upsell
        return True

    @staticmethod
    def _tidy(text: str) -> str:
        text = re.sub(r"\(\s*\)", "", text)
        text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)  # keeps list indentation
        text = re.sub(r"[ \t]+(?=[.,;:!?)])", "", text)
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
        return re.sub(r"\n{3,}", "\n\n", text)
