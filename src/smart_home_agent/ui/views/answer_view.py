import streamlit as st

from smart_home_agent.answer_tags import (
    CompareBlock,
    CompatibilityBlock,
    ItemsBlock,
    PlainTextRenderer,
    TagParser,
    TextSegment,
    UpgradeBlock,
)
from smart_home_agent.models import RichContent
from smart_home_agent.ui.backend import ImageAvailability
from smart_home_agent.ui.components import (
    AnswerMarkdown,
    ComparisonHtml,
    CompatibilityHtml,
    ProductCardHtml,
    UpgradeHtml,
)


class AnswerView:
    """An answer's text with its answer tags replaced by catalog components."""

    @staticmethod
    def render(text: str, content: RichContent | None) -> None:
        """A tag without resolved data is dropped (blocks) or shown as its id (inline); the raw tag is never
        shown. Without resolved content the answer is plain text."""
        if content is None:
            st.markdown(PlainTextRenderer({}).render(text))
            return
        segments = TagParser.parse(text)
        in_blocks = TagParser.block_ids(segments)
        missing = ImageAvailability.missing_for(list(content.products.values()))  # one cached check per answer
        for segment in segments:
            match segment:
                case TextSegment(body):
                    markdown = AnswerMarkdown.render(body, content.products, in_blocks, missing)
                    st.markdown(markdown, unsafe_allow_html=True)
                case ItemsBlock(ids):
                    products = [content.products[pid] for pid in ids if pid in content.products]
                    if products:
                        st.html(ProductCardHtml.cards(products, missing))
                case CompareBlock(ids):
                    if (comparison := content.comparisons.get(RichContent.compare_key(ids))) is not None:
                        st.html(ComparisonHtml.render(comparison))
                case CompatibilityBlock(product_id):
                    if (compatibility := content.compatibility.get(product_id)) is not None:
                        st.html(CompatibilityHtml.render(content.products[product_id], compatibility))
                case UpgradeBlock(from_id, to_id):
                    if (upsell := content.upgrades.get(RichContent.upgrade_key(from_id, to_id))) is not None:
                        st.html(UpgradeHtml.render(content.products[from_id], content.products[to_id], upsell))
