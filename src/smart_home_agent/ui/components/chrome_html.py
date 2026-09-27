from smart_home_agent.ui.components._templates import Templates


class ChromeHtml:
    """The fixed page frame: masthead brand, welcome intro and the advisor's eyebrow above each answer."""

    CAPABILITIES = ("Recommend", "Compare", "Check compatibility", "Show sources")

    @staticmethod
    def masthead() -> str:
        """The brand part of the masthead; its buttons (new conversation, cart) are Streamlit widgets beside it."""
        return Templates.render("chrome", "masthead")

    @staticmethod
    def intro() -> str:
        return Templates.render("chrome", "intro", capabilities=ChromeHtml.CAPABILITIES)

    @staticmethod
    def assistant_eyebrow() -> str:
        return Templates.render("chrome", "assistant_eyebrow")
