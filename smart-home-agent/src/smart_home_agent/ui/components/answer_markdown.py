from collections.abc import Collection, Mapping

from smart_home_agent.answer_tags import ProseRenderer
from smart_home_agent.models import Product
from smart_home_agent.ui.components.item_chip_html import ItemChipHtml


class AnswerMarkdown:
    """One text segment of an answer as markdown for `st.markdown(unsafe_allow_html=True)`."""

    @staticmethod
    def render(
        body: str,
        products: Mapping[str, Product],
        shown_in_blocks: Collection[str] = (),
        missing_images: frozenset[str] = frozenset(),
    ) -> str:
        """The model's text has its "<" escaped (so it can never inject HTML), and each inline <item/> becomes
        a chip."""
        body = ProseRenderer.strip_echoed_titles(body, {pid: p.title for pid, p in products.items()})
        return ProseRenderer.render(
            body,
            lambda text: text.replace("<", "&lt;"),
            lambda pid: ItemChipHtml.render(products.get(pid), pid, pid in shown_in_blocks, missing_images),
        )
