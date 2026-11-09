"""Pure HTML builders for the UI: no Streamlit import, so every component can be tested as a string.

Every dynamic value is escaped, and the data comes from the catalog (resolved by the services), never from the
model's text. Each class renders one component:

- page frame: `ChromeHtml` (masthead, intro, advisor eyebrow), `SuggestionTileHtml` (welcome tiles),
  `ProgressHtml` (typing cue, tool status), `NoticeHtml` (failure notice, cart decision in the history);
- answer tags: `AnswerMarkdown` (text with inline `ItemChipHtml` chips), `ProductCardHtml` (<items>),
  `ComparisonHtml` (<compare>), `CompatibilityHtml` (<compatibility>), `UpgradeHtml` (<upgrade>);
- customer panel and cart: `SetupPanelHtml`, `CartHtml`, `ConfirmationHtml` (with `ConfirmationState`).

The markup lives in Jinja2 templates (`templates/`, one file per component, one macro per public method, shared
pieces in `_macros.html.j2`), rendered with autoescape by the private `_templates`; `_compact_source` strips the
template layout so the output stays on one line. Formatting filters live in `_markup`, fixed texts in `_texts`.
"""

from smart_home_agent.ui.components.answer_markdown import AnswerMarkdown
from smart_home_agent.ui.components.cart_html import CartHtml
from smart_home_agent.ui.components.chrome_html import ChromeHtml
from smart_home_agent.ui.components.comparison_html import ComparisonHtml
from smart_home_agent.ui.components.compatibility_html import CompatibilityHtml
from smart_home_agent.ui.components.confirmation_html import ConfirmationHtml
from smart_home_agent.ui.components.confirmation_state import ConfirmationState
from smart_home_agent.ui.components.item_chip_html import ItemChipHtml
from smart_home_agent.ui.components.notice_html import NoticeHtml
from smart_home_agent.ui.components.product_card_html import ProductCardHtml
from smart_home_agent.ui.components.progress_html import ProgressHtml
from smart_home_agent.ui.components.setup_panel_html import SetupPanelHtml
from smart_home_agent.ui.components.suggestion import Suggestion
from smart_home_agent.ui.components.suggestion_tile_html import SuggestionTileHtml
from smart_home_agent.ui.components.upgrade_html import UpgradeHtml

__all__ = [
    "AnswerMarkdown",
    "CartHtml",
    "ChromeHtml",
    "ComparisonHtml",
    "CompatibilityHtml",
    "ConfirmationHtml",
    "ConfirmationState",
    "ItemChipHtml",
    "NoticeHtml",
    "ProductCardHtml",
    "ProgressHtml",
    "SetupPanelHtml",
    "Suggestion",
    "SuggestionTileHtml",
    "UpgradeHtml",
]
