from collections.abc import Mapping

from smart_home_agent.answer_tags.prose_renderer import ProseRenderer
from smart_home_agent.answer_tags.segments import ItemsBlock, TextSegment
from smart_home_agent.answer_tags.tag_parser import TagParser


class PlainTextRenderer:
    """Text-only rendering (terminal chat, or when no data could be resolved): never shows raw tags.
    Like the web interface, an inline <item/> shows the catalog title (the model names the version in its
    own words) and an <items> list shows `names` (title plus version label, the cards' subtitle line)."""

    def __init__(self, titles: Mapping[str, str], names: Mapping[str, str] | None = None) -> None:
        self._titles = titles
        self._names = names or {}

    def render(self, text: str) -> str:
        parts = []
        for segment in TagParser.parse(text):
            match segment:
                case TextSegment(body):
                    parts.append(
                        ProseRenderer.replace_items(ProseRenderer.strip_echoed_titles(body, self._titles), self._title)
                    )
                case ItemsBlock(ids):
                    parts.append("\n".join(f"- {self._name(pid)}" for pid in ids))
        return "\n\n".join(parts)

    def _title(self, pid: str) -> str:
        return self._titles.get(pid) or pid

    def _name(self, pid: str) -> str:
        return self._names.get(pid) or self._title(pid)
