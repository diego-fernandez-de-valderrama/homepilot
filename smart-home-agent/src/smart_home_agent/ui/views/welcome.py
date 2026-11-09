import streamlit as st

from smart_home_agent.ui.components import ChromeHtml, Suggestion, SuggestionTileHtml


class Welcome:
    """The empty state: the intro and clickable example requests."""

    SUGGESTIONS = (
        Suggestion(
            "thermostat", "Heating", "Thermostat for Google Home", "I need a thermostat compatible with Google Home."
        ),
        Suggestion(
            "sensors", "Security", "HomeKit motion sensor", "I have HomeKit and I'm looking for a motion sensor."
        ),
        Suggestion("euro", "Budget", "Alexa, max 150 €", "Ich suche etwas für Alexa, das nicht mehr als 150 € kostet."),
    )

    @staticmethod
    def render() -> str | None:
        """The prompt of the tile the customer clicked, if any."""
        with st.empty().container():
            st.html(ChromeHtml.intro())
            return Welcome._tiles()

    @staticmethod
    def _tiles() -> str | None:
        """Each tile is an HTML card with an invisible full-size button over it."""
        st.html('<p class="hp-section-label">Start with an example</p>')
        selected = None
        columns = st.columns(len(Welcome.SUGGESTIONS))
        for i, (column, suggestion) in enumerate(zip(columns, Welcome.SUGGESTIONS, strict=True)):
            with column, st.container(key=f"hp-tile-{i}"):
                st.html(SuggestionTileHtml.render(suggestion))
                if st.button(suggestion.title, key=f"hp-suggest-{i}", width="stretch"):
                    selected = suggestion.prompt
        return selected
