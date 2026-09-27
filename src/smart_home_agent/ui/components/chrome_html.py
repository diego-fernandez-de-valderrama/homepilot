class ChromeHtml:
    """The fixed page frame: masthead brand, welcome intro and the advisor's eyebrow above each answer."""

    @staticmethod
    def masthead() -> str:
        """The brand part of the masthead; its buttons (new conversation, cart) are Streamlit widgets beside it."""
        return (
            '<header class="hp-masthead">'
            '<div class="hp-masthead__mark" aria-hidden="true"></div>'
            '<div class="hp-masthead__brand">'
            '<span class="hp-masthead__name">HomePilot</span>'
            '<span class="hp-masthead__tag">Smart home advisor · Smart-Home-Beratung</span>'
            "</div>"
            '<span class="hp-masthead__meta">Catalog-verified answers</span>'
            "</header>"
        )

    @staticmethod
    def intro() -> str:
        capabilities = ("Recommend", "Compare", "Check compatibility", "Show sources")
        items = "".join(f"<li>{c}</li>" for c in capabilities)
        return (
            '<section class="hp-intro">'
            '<p class="hp-eyebrow">Your digital advisor</p>'
            '<h2 class="hp-intro__title">What are you planning for your home?</h2>'
            '<p class="hp-intro__lead">Tell me what you already use (Alexa, HomeKit, Google Home, Zigbee...) and '
            "your budget. Every price and compatibility claim comes from the catalog.</p>"
            f'<ul class="hp-capabilities">{items}</ul>'
            "</section>"
        )

    @staticmethod
    def assistant_eyebrow() -> str:
        return '<p class="hp-eyebrow hp-eyebrow--advisor">HomePilot · Advisor</p>'
