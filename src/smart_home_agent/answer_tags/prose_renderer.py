import re
from collections.abc import Callable, Mapping

from smart_home_agent.answer_tags import _patterns
from smart_home_agent.answer_tags._code_fences import CodeFences


class ProseRenderer:
    """Renders the inline <item/> tags of a text segment; code fences stay unchanged."""

    @staticmethod
    def render(text: str, render_text: Callable[[str], str], render_item: Callable[[str], str]) -> str:
        """Every run of text goes through `render_text` and every inline <item/> through `render_item(product_id)`."""
        out: list[str] = []
        for part, is_code in CodeFences.split(text):
            if is_code:
                out.append(part)
                continue
            pieces = _patterns.ITEM.split(part)  # the id group is captured: odd positions are product ids
            out += [render_item(piece) if i % 2 else render_text(piece) for i, piece in enumerate(pieces)]
        return "".join(out)

    @staticmethod
    def replace_items(text: str, render: Callable[[str], str]) -> str:
        """Replaces every inline <item/> outside code fences by `render(product_id)`."""
        return ProseRenderer.render(text, lambda piece: piece, render)

    @staticmethod
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
            # "Title (<item/>)" and "Title <item/>": the parentheses go only as a pair, never one of them alone.
            text = re.sub(
                rf"{name}[ \t]*[:,-]?[ \t]*(?:\(({tag})\)|({tag}))",
                lambda m: m[1] or m[2],
                text,
                flags=re.IGNORECASE,
            )
        return text
