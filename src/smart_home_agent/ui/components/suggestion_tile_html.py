import html

from smart_home_agent.ui.components.suggestion import Suggestion


class SuggestionTileHtml:
    """The card of a welcome tile (an invisible full-size button is laid over it)."""

    @staticmethod
    def render(suggestion: Suggestion) -> str:
        return (
            '<div class="hp-tile">'
            f'<span class="hp-tile__icon">{html.escape(suggestion.icon)}</span>'
            f'<span class="hp-tile__kicker">{html.escape(suggestion.kicker)}</span>'
            f'<span class="hp-tile__title">{html.escape(suggestion.title)}</span>'
            f'<span class="hp-tile__prompt">"{html.escape(suggestion.prompt)}"</span>'
            '<span class="hp-tile__cta">Ask</span>'
            "</div>"
        )
