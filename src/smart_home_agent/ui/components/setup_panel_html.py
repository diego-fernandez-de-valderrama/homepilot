import html

from catalog_ingestion.vocabulary import categories as category_vocabulary

from smart_home_agent.services import Vocabulary
from smart_home_agent.session import SessionState
from smart_home_agent.ui.components._markup import Markup
from smart_home_agent.ui.components._texts import LANGUAGES


class SetupPanelHtml:
    """The customer panel's "Your setup" block: only what the session already knows, never inferred."""

    @staticmethod
    def render(state: SessionState | None) -> str:
        rows = SetupPanelHtml._rows(state) if state is not None else []
        if not rows:
            body = '<p class="hp-setup__empty">Tell me about your setup: ecosystem, voice assistant, budget, hubs.</p>'
        else:
            body = "".join(
                f'<div class="hp-setup__row"><span class="hp-setup__key">{html.escape(key)}</span>'
                f'<div class="hp-setup__values">{Markup.chips(values)}</div></div>'
                for key, values in rows
            )
        return f'<section class="hp-setup"><p class="hp-panel-label">Your setup</p>{body}</section>'

    @staticmethod
    def _rows(state: SessionState) -> list[tuple[str, list[str]]]:
        rows: list[tuple[str, list[str]]] = []
        if state.must_support:
            rows.append(("Works with", [Vocabulary.label(term) for term in state.must_support]))
        if state.owned_devices is not None:
            owned = [Vocabulary.requirement_label(d) for d in state.owned_devices]
            rows.append(("Hubs owned", owned or ["None"]))
        if state.budget_max is not None:
            rows.append(("Budget", [SetupPanelHtml._budget(state.budget_max)]))
        if state.current_category:
            rows.append(("Looking at", [SetupPanelHtml._category_label(state.current_category)]))
        if state.requirements:
            rows.append(("Needs", state.requirements))
        if state.language in LANGUAGES:
            rows.append(("Language", [LANGUAGES[state.language]]))
        return rows

    @staticmethod
    def _budget(value: float) -> str:
        return f"up to {value:,.0f} €" if value == int(value) else f"up to {value:,.2f} €"

    @staticmethod
    def _category_label(key: str) -> str:
        category = category_vocabulary.category_by_key(key)
        return category.label_en if category else key
