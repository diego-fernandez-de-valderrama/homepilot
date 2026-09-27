from pathlib import Path

import streamlit as st

_ASSETS = Path(__file__).parent / "assets"


class PageAssets:
    """Our own static files: the advisor avatar, the stylesheet and the hover-card script."""

    ADVISOR_AVATAR = str(_ASSETS / "advisor.svg")

    @staticmethod
    def inject() -> None:
        PageAssets.inject_styles()
        PageAssets.inject_behaviour()

    @staticmethod
    def inject_styles() -> None:
        st.html(f"<style>{(_ASSETS / 'styles.css').read_text(encoding='utf-8')}</style>")

    @staticmethod
    def inject_behaviour() -> None:
        """Our own static script (never model output): flips a chip's hover card downward when it does not fit
        above. JavaScript must be allowed explicitly for st.html; the answer text stays escaped."""
        script = (_ASSETS / "item_card.js").read_text(encoding="utf-8")
        st.html(f"<script>{script}</script>", unsafe_allow_javascript=True)
