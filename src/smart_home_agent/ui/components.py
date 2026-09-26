"""Presentation helpers for the Streamlit UI: stylesheet, masthead, empty state and sidebar setup panel.

Presentation only. The HTML builders are pure functions (easy to test); every dynamic value is escaped.
The setup panel only shows what the agent already stored in the session state.
"""

import html
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from catalog_ingestion.vocabulary import categories as category_vocabulary

from smart_home_agent.agent.state import SessionState
from smart_home_agent.services import vocabulary

_UI_DIR = Path(__file__).parent
ADVISOR_AVATAR = str(_UI_DIR / "assets" / "advisor.svg")

_LANGUAGES = {"en": "English", "de": "Deutsch"}


@dataclass(frozen=True, slots=True)
class Suggestion:
    icon: str  # Material Symbols name, e.g. "thermostat"
    kicker: str  # short topic label above the title
    title: str
    prompt: str  # sent to the agent as the user's message


def inject_styles() -> None:
    st.html(f"<style>{(_UI_DIR / 'styles.css').read_text(encoding='utf-8')}</style>")


def masthead_html() -> str:
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


def intro_html() -> str:
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


def suggestion_tile_html(suggestion: Suggestion) -> str:
    return (
        '<div class="hp-tile">'
        f'<span class="hp-tile__icon">{html.escape(suggestion.icon)}</span>'
        f'<span class="hp-tile__kicker">{html.escape(suggestion.kicker)}</span>'
        f'<span class="hp-tile__title">{html.escape(suggestion.title)}</span>'
        f'<span class="hp-tile__prompt">"{html.escape(suggestion.prompt)}"</span>'
        '<span class="hp-tile__cta">Ask</span>'
        "</div>"
    )


def suggestion_tiles(suggestions: list[Suggestion]) -> str | None:
    """Clickable entry tiles. Each tile is an HTML card with an invisible full-size button over it."""
    st.html('<p class="hp-section-label">Start with an example</p>')
    selected = None
    for i, (column, suggestion) in enumerate(zip(st.columns(len(suggestions)), suggestions, strict=True)):
        with column, st.container(key=f"hp-tile-{i}"):
            st.html(suggestion_tile_html(suggestion))
            if st.button(suggestion.title, key=f"hp-suggest-{i}", width="stretch"):
                selected = suggestion.prompt
    return selected


def assistant_eyebrow_html() -> str:
    return '<p class="hp-eyebrow hp-eyebrow--advisor">HomePilot · Advisor</p>'


def _chips(values: list[str]) -> str:
    return "".join(f'<span class="hp-chip">{html.escape(v)}</span>' for v in values)


def _category_label(key: str) -> str:
    category = category_vocabulary.category_by_key(key)
    return category.label_en if category else key


def _format_budget(value: float) -> str:
    return f"up to {value:,.0f} €" if value == int(value) else f"up to {value:,.2f} €"


def setup_panel_html(state: SessionState | None) -> str:
    """The sidebar "Your setup" block: only what the session already knows, never inferred."""
    rows: list[tuple[str, list[str]]] = []
    if state is not None:
        if state.must_support:
            rows.append(("Works with", [vocabulary.label(term) for term in state.must_support]))
        if state.owned_devices is not None:
            owned = [vocabulary.requirement_label(d) for d in state.owned_devices]
            rows.append(("Hubs owned", owned or ["None"]))
        if state.budget_max is not None:
            rows.append(("Budget", [_format_budget(state.budget_max)]))
        if state.current_category:
            rows.append(("Looking at", [_category_label(state.current_category)]))
        if state.requirements:
            rows.append(("Needs", state.requirements))
        if state.language in _LANGUAGES:
            rows.append(("Language", [_LANGUAGES[state.language]]))
    if not rows:
        body = '<p class="hp-setup__empty">Tell me about your setup: ecosystem, voice assistant, budget, hubs.</p>'
    else:
        body = "".join(
            f'<div class="hp-setup__row"><span class="hp-setup__key">{html.escape(key)}</span>'
            f'<div class="hp-setup__values">{_chips(values)}</div></div>'
            for key, values in rows
        )
    return f'<section class="hp-setup"><p class="hp-rail-label">Your setup</p>{body}</section>'
