from smart_home_agent.ui.components._templates import Templates
from smart_home_agent.ui.components.suggestion import Suggestion


class SuggestionTileHtml:
    """The card of a welcome tile (an invisible full-size button is laid over it)."""

    @staticmethod
    def render(suggestion: Suggestion) -> str:
        return Templates.render("suggestion_tile", "render", suggestion=suggestion)
