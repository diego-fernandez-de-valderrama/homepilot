"""Presentation helpers for the Streamlit UI: stylesheet, masthead, empty state, sidebar setup and cart panels,
the cart confirmation card and the product components behind the answer tags (cards, comparison,
compatibility, upgrade).

Presentation only. The HTML builders are pure functions (easy to test); every dynamic value is escaped.
The setup panel only shows what the agent already stored in the session state.
"""

import html
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import streamlit as st
from catalog_ingestion.domain.enums import FactStatus
from catalog_ingestion.vocabulary import categories as category_vocabulary

from smart_home_agent.agent.state import SessionState
from smart_home_agent.models import rich
from smart_home_agent.models.cart import CartChangeLine, CartConfirmation, CartLine, CartView
from smart_home_agent.models.comparison import NOT_LISTED, ComparisonResult
from smart_home_agent.models.product import Product
from smart_home_agent.models.recommendation import UpsellSuggestion
from smart_home_agent.models.rich import ProductCompatibility
from smart_home_agent.services import vocabulary

_UI_DIR = Path(__file__).parent
ADVISOR_AVATAR = str(_UI_DIR / "assets" / "advisor.svg")

_LANGUAGES = {"en": "English", "de": "Deutsch"}

# Progress labels per tool. Shown only once the model really calls that tool in the current turn.
_TOOL_LABELS = {
    "recommend_products": "Finding matching products in the catalog",
    "search_products": "Searching the catalog",
    "filter_products": "Filtering the catalog",
    "get_product": "Loading product details",
    "check_compatibility": "Checking compatibility",
    "compare_products": "Comparing products",
    "get_evidence": "Looking up the sources",
    "remember_preferences": "Noting your preferences",
    "remember_customer_facts": "Remembering what you told me",
    "view_cart": "Checking your cart",
    "add_to_cart": "Preparing the change to your cart",
    "remove_from_cart": "Preparing the change to your cart",
}

# Neutral "the advisor is writing" cue: no text, so it never claims work that is not happening.
TYPING_HTML = (
    '<div class="hp-typing" role="status" aria-label="HomePilot is answering">'
    "<span></span><span></span><span></span></div>"
)


@dataclass(frozen=True, slots=True)
class Suggestion:
    icon: str  # Material Symbols name, e.g. "thermostat"
    kicker: str  # short topic label above the title
    title: str
    prompt: str  # sent to the agent as the user's message


def inject_styles() -> None:
    st.html(f"<style>{(_UI_DIR / 'styles.css').read_text(encoding='utf-8')}</style>")


def inject_behaviour() -> None:
    """Our own static script (never model output): flips a chip's hover card downward when it does not fit
    above. JavaScript must be allowed explicitly for st.html; the answer text stays escaped."""
    script = (_UI_DIR / "item_card.js").read_text(encoding="utf-8")
    st.html(f"<script>{script}</script>", unsafe_allow_javascript=True)


def masthead_html(cart_count: int = 0) -> str:
    """`cart_count`: units in the cart, shown as a badge (the cart itself lives in the sidebar)."""
    label = f"{cart_count} item{'s' if cart_count != 1 else ''} in your cart"
    badge_class = "hp-cart-badge hp-cart-badge--filled" if cart_count else "hp-cart-badge"
    return (
        '<header class="hp-masthead">'
        '<div class="hp-masthead__mark" aria-hidden="true"></div>'
        '<div class="hp-masthead__brand">'
        '<span class="hp-masthead__name">HomePilot</span>'
        '<span class="hp-masthead__tag">Smart home advisor · Smart-Home-Beratung</span>'
        "</div>"
        '<span class="hp-masthead__meta">Catalog-verified answers</span>'
        f'<span class="{badge_class}" title="{label}" aria-label="{label}">'
        '<span class="hp-cart-badge__icon" aria-hidden="true">shopping_cart</span>'
        f'<span class="hp-cart-badge__count">{cart_count}</span></span>'
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


def tool_status_label(tool_name: str) -> str:
    return _TOOL_LABELS.get(tool_name, "Working on your request")


def tool_progress_html(label: str) -> str:
    return (
        '<div class="hp-progress" role="status"><span class="hp-progress__spinner"></span>'
        f"<span>{html.escape(label)}</span></div>"
    )


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


# ---------- Answer components (data from the catalog only, never from the model's text) ----------

# Customer wording per status: "unknown" is "not confirmed", never "compatible" or "incompatible".
_STATUS_TEXT = {
    FactStatus.SUPPORTED: "Supported",
    FactStatus.UNKNOWN: "Not confirmed",
    FactStatus.UNSUPPORTED: "Not supported",
}
_OVERALL_TEXT = {
    FactStatus.SUPPORTED: "Works with your setup",
    FactStatus.UNKNOWN: "Not confirmed for your setup",
    FactStatus.UNSUPPORTED: "Not compatible with your setup",
}
_REQUIREMENT_TEXT = {"satisfied": "you have it", "missing": "not in your setup", "unverified": "check if you have it"}


def format_price(value: float | None) -> str:
    return f"{value:,.2f} €" if value is not None else "price not listed"


_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#+!|$~])")


def _markdown_literal(value: str) -> str:
    """Text placed between HTML tags inside markdown is still parsed as markdown: neutralize its syntax."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", html.escape(value))


def _image_html(product: Product, missing_images: frozenset[str], css_class: str) -> str:
    image_url = safe_url(product.image_url)
    if image_url and image_url not in missing_images:
        return f'<img class="{css_class}" src="{html.escape(image_url)}" alt="" loading="lazy">'
    return f'<span class="{css_class} {css_class}--empty"><span>No image</span></span>'


def item_chip_html(
    product: Product | None, product_id: str, shown_in_block: bool = False, missing_images: frozenset[str] = frozenset()
) -> str:
    """Inline <item/>: a chip with the catalog name (and price, unless a block of the same answer already
    shows the product) that reveals a mini product card on hover or keyboard focus. One line of inline HTML
    inside markdown, so only <span>, <img> and <a> are used. The bare id when the product is unknown."""
    if product is None:
        return _markdown_literal(product_id)
    price = format_price(product.price)
    price_html = "" if shown_in_block else f'<span class="hp-item__price">{_markdown_literal(price)}</span>'
    brand = f'<span class="hp-item__brand">{_markdown_literal(product.brand)}</span>' if product.brand else ""
    source_url = safe_url(product.source_url)
    link = (
        f'<a class="hp-item__link" href="{html.escape(source_url)}" target="_blank" rel="noopener">View in shop</a>'
        if source_url
        else ""
    )
    card = (
        '<span class="hp-item__card" role="tooltip">'
        f"{_image_html(product, missing_images, 'hp-item__image')}{brand}"
        f'<span class="hp-item__title">{_markdown_literal(product.title)}</span>'
        f'<span class="hp-item__card-price">{_markdown_literal(price)}</span>{link}</span>'
    )
    return (
        f'<span class="hp-item" tabindex="0"><span class="hp-item__name">{_markdown_literal(product.title)}</span>'
        f"{price_html}{card}</span>"
    )


def answer_markdown(
    body: str,
    products: Mapping[str, Product],
    shown_in_blocks: Collection[str] = (),
    missing_images: frozenset[str] = frozenset(),
) -> str:
    """Markdown of one text segment for `st.markdown(unsafe_allow_html=True)`: the model's text has its "<"
    escaped (so it can never inject HTML), and each inline <item/> becomes a chip."""
    body = rich.strip_echoed_titles(body, {pid: p.title for pid, p in products.items()})
    return rich.render_prose(
        body,
        lambda text: text.replace("<", "&lt;"),
        lambda pid: item_chip_html(products.get(pid), pid, pid in shown_in_blocks, missing_images),
    )


def safe_url(url: str | None) -> str | None:
    return url if url and url.startswith(("https://", "http://")) else None


def card_image_urls(products: list[Product]) -> tuple[str, ...]:
    """The image URLs the product cards would load (the ones worth checking for availability)."""
    return tuple(dict.fromkeys(url for p in products if (url := safe_url(p.image_url))))


def _product_card(product: Product, missing_images: frozenset[str]) -> str:
    image = _image_html(product, missing_images, "hp-card__image")
    brand = f'<span class="hp-card__brand">{html.escape(product.brand)}</span>' if product.brand else ""
    was = (
        f'<s class="hp-card__was">{html.escape(format_price(product.original_price))}</s>'
        if product.original_price and product.price is not None and product.original_price > product.price
        else ""
    )
    source_url = safe_url(product.source_url)
    link = (
        f'<a class="hp-card__link" href="{html.escape(source_url)}" target="_blank" rel="noopener">View in shop</a>'
        if source_url
        else ""
    )
    return (
        '<article class="hp-card">'
        f"{image}{brand}"
        f'<span class="hp-card__title">{html.escape(product.title)}</span>'
        f'<span class="hp-card__price">{html.escape(format_price(product.price))}{was}</span>'
        f"{link}</article>"
    )


def product_cards_html(products: list[Product], missing_images: frozenset[str] = frozenset()) -> str:
    """`missing_images`: image URLs known to be gone; those cards show a placeholder instead of a blank box."""
    return f'<div class="hp-cards">{"".join(_product_card(p, missing_images) for p in products)}</div>'


def _cell(group: str, value: str) -> str:
    status = value.split(" ", 1)[0]
    if group != "compatibility" or status not in FactStatus:
        return f"<td>{html.escape(value)}</td>"
    return f'<td class="hp-compare__status hp-compare__status--{status}">{_STATUS_TEXT[FactStatus(status)]}</td>'


def comparison_html(result: ComparisonResult) -> str:
    """Rows where every product is "not listed" are left out; other "not listed" values stay verbatim."""
    head = "".join(
        f'<th scope="col">{html.escape(p.title)}<span class="hp-compare__price">{html.escape(format_price(p.price))}'
        "</span></th>"
        for p in result.products
    )
    rows = "".join(
        ('<tr class="hp-compare__differs">' if row.differs else "<tr>")
        + f'<th scope="row">{html.escape(row.attribute)}</th>'
        + "".join(_cell(row.group, v) for v in row.values)
        + "</tr>"
        for row in result.rows
        if any(v != NOT_LISTED for v in row.values) and row.attribute != "data completeness"
    )
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in result.notes)
    return (
        '<div class="hp-compare"><table>'
        f"<thead><tr><td></td>{head}</tr></thead><tbody>{rows}</tbody></table>"
        f'<ul class="hp-compare__notes">{notes}</ul></div>'
    )


def compatibility_html(product: Product, compatibility: ProductCompatibility) -> str:
    result = compatibility.result
    heading = (
        f'<p class="hp-compat__overall hp-compat__overall--{result.overall.value}">'
        f"{html.escape(_OVERALL_TEXT[result.overall])}</p>"
        if compatibility.against_setup and result.checks
        else '<p class="hp-compat__overall">Compatibility listed in the catalog</p>'
    )
    chips = (
        "".join(
            f'<span class="hp-compat-chip hp-compat-chip--{c.status.value}">{html.escape(c.label)}'
            f'<span class="hp-compat-chip__status">{html.escape(_STATUS_TEXT[c.status])}</span></span>'
            for c in result.checks
        )
        or '<span class="hp-compat__empty">The catalog lists no compatibility information.</span>'
    )
    requirements = [
        f"Requires {r.label}" + (f" ({_REQUIREMENT_TEXT[r.status]})" if r.status in _REQUIREMENT_TEXT else "")
        for r in result.requirements
        if r.status != "info"
    ]
    if result.requires_professional_installation:
        requirements.append("Installation by a qualified electrician required")
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in requirements)
    return (
        '<section class="hp-compat">'
        f'<p class="hp-compat__title">{html.escape(product.title)}</p>{heading}'
        f'<div class="hp-compat__chips">{chips}</div>'
        + (f'<ul class="hp-compat__notes">{notes}</ul>' if notes else "")
        + "</section>"
    )


def upgrade_html(base: Product, target: Product, upsell: UpsellSuggestion) -> str:
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in upsell.upgrade_reasons)
    return (
        '<section class="hp-upgrade">'
        '<p class="hp-eyebrow">Upgrade option</p>'
        '<div class="hp-upgrade__pair">'
        f'<div class="hp-upgrade__product"><span class="hp-upgrade__label">Your match</span>'
        f"<span>{html.escape(base.title)}</span><span>{html.escape(format_price(base.price))}</span></div>"
        '<span class="hp-upgrade__arrow" aria-hidden="true">→</span>'
        f'<div class="hp-upgrade__product"><span class="hp-upgrade__label">Upgrade</span>'
        f"<span>{html.escape(target.title)}</span><span>{html.escape(format_price(target.price))}</span></div>"
        "</div>"
        f'<p class="hp-upgrade__delta">+{html.escape(format_price(upsell.price_difference))}</p>'
        + (f'<ul class="hp-upgrade__reasons">{reasons}</ul>' if reasons else "")
        + "</section>"
    )


# ---------- Shopping cart (sidebar panel and confirmation card) ----------


def _thumb_html(product: Product | None, missing_images: frozenset[str], css_class: str) -> str:
    """Cart and confirmation thumbnails: the product image, or a quiet package glyph when there is none
    (a missing image is not information for the customer, so no "No image" text)."""
    image_url = safe_url(product.image_url) if product else None
    if image_url and image_url not in missing_images:
        return f'<img class="{css_class}" src="{html.escape(image_url)}" alt="" loading="lazy">'
    return (
        f'<span class="{css_class} {css_class}--empty" aria-hidden="true">'
        '<span class="hp-thumb-glyph">inventory_2</span></span>'
    )


def cart_header_html(view: CartView) -> str:
    count = f'<span class="hp-cart__count">{view.item_count}</span>' if view.item_count else ""
    empty = (
        '<p class="hp-cart__empty">Your cart is empty. Ask HomePilot to add a product.</p>' if not view.lines else ""
    )
    return f'<div class="hp-cart"><p class="hp-rail-label hp-cart__label">Your cart{count}</p>{empty}</div>'


def cart_line_html(line: CartLine, missing_images: frozenset[str] = frozenset()) -> str:
    """One cart line (the stepper buttons are Streamlit widgets rendered right below it)."""
    product = line.product
    if product is None:
        return (
            '<div class="hp-cart__line hp-cart__line--gone">'
            f"{_thumb_html(None, missing_images, 'hp-cart__thumb')}"
            f'<div class="hp-cart__info"><span class="hp-cart__title">Product {html.escape(line.product_id)}</span>'
            '<span class="hp-cart__note">No longer available</span></div></div>'
        )
    brand = f'<span class="hp-cart__brand">{html.escape(product.brand)}</span>' if product.brand else ""
    subtotal = (
        f'<span class="hp-cart__subtotal">{line.quantity} × {html.escape(format_price(line.unit_price))}</span>'
        if line.quantity > 1 and line.unit_price is not None
        else ""
    )
    return (
        '<div class="hp-cart__line">'
        f"{_thumb_html(product, missing_images, 'hp-cart__thumb')}"
        f'<div class="hp-cart__info">{brand}<span class="hp-cart__title">{html.escape(product.title)}</span>'
        f'<span class="hp-cart__price">{html.escape(format_price(line.line_total))}</span>{subtotal}</div></div>'
    )


def cart_total_html(view: CartView) -> str:
    note = '<p class="hp-cart__note">Some prices are not listed and not included.</p>' if view.has_unpriced else ""
    return (
        '<div class="hp-cart__total"><span>Total</span>'
        f'<span class="hp-cart__total-value">{html.escape(format_price(view.total))}</span></div>{note}'
    )


# Card state after the customer's decision (None: still open). "expired": a new message was sent instead.
ConfirmationState = Literal["confirmed", "cancelled", "expired"] | None

_CONFIRM_STATE_TEXT = {
    ("add", "confirmed"): "Added to your cart",
    ("remove", "confirmed"): "Removed from your cart",
    ("add", "cancelled"): "Not added",
    ("remove", "cancelled"): "Not removed",
}


def _confirmation_line_html(
    confirmation: CartConfirmation, line: CartChangeLine, missing_images: frozenset[str]
) -> str:
    product = line.product
    amount = str(line.quantity) if line.quantity is not None else (f"All {line.in_cart}" if line.in_cart > 1 else "1")
    price = product.price if product else None
    detail = f"{amount} × {format_price(price)}"
    if price is not None and line.units > 1:
        detail += f" = {format_price(round(price * line.units, 2))}"
    in_cart = f"In your cart now: {line.in_cart} · after this change: {confirmation.after(line)}"
    title = product.title if product else f"Product {line.product_id} (not in the catalog)"
    return (
        f'<li class="hp-confirm__body">{_thumb_html(product, missing_images, "hp-confirm__image")}'
        f'<div class="hp-confirm__info"><span class="hp-confirm__title">{html.escape(title)}</span>'
        f'<span class="hp-confirm__detail">{html.escape(detail)}</span>'
        f'<span class="hp-confirm__cart">{html.escape(in_cart)}</span></div></li>'
    )


def confirm_button_label(confirmation: CartConfirmation) -> str:
    count = len(confirmation.lines)
    if confirmation.action == "add":
        return "Add to cart" if count == 1 else f"Add {count} products"
    return "Remove" if count == 1 else f"Remove {count} products"


def cart_confirmation_html(
    confirmation: CartConfirmation, state: ConfirmationState = None, missing_images: frozenset[str] = frozenset()
) -> str:
    """The change the advisor proposes (one or more products, confirmed together), from catalog data only;
    the buttons are rendered below it."""
    adding = confirmation.action == "add"
    count = len(confirmation.lines)
    eyebrow = ("Add to cart" if adding else "Remove from cart") + (f" · {count} products" if count > 1 else "")
    lines = "".join(_confirmation_line_html(confirmation, line, missing_images) for line in confirmation.lines)
    total = ""
    if count > 1 and confirmation.total is not None:
        sign = "+" if adding else "−"
        total = (
            '<p class="hp-confirm__total"><span>Change total</span>'
            f'<span class="hp-confirm__total-value">{sign}{html.escape(format_price(confirmation.total))}</span></p>'
        )
    if state is None:
        status = ""
    elif state == "expired":
        status = '<span class="hp-confirm__state hp-confirm__state--expired">Not confirmed</span>'
    else:
        text = _CONFIRM_STATE_TEXT[(confirmation.action, state)]
        status = f'<span class="hp-confirm__state hp-confirm__state--{state}">{html.escape(text)}</span>'
    modifier = "add" if adding else "remove"
    return (
        f'<section class="hp-confirm hp-confirm--{modifier}{" hp-confirm--done" if state else ""}">'
        f'<p class="hp-eyebrow">{eyebrow}</p><ul class="hp-confirm__lines">{lines}</ul>{total}{status}</section>'
    )


def confirmation_lead_html(count: int) -> str:
    text = "Please confirm this change to your cart." if count == 1 else "Please confirm these changes to your cart."
    return f'<p class="hp-confirm-lead">{text}</p>'


_FAILURE_TEXT = {
    "en": ("Sorry, I couldn't finish my answer.", "Please send your message again in a moment."),
    "de": (
        "Entschuldigung, ich konnte meine Antwort nicht fertigstellen.",
        "Bitte senden Sie Ihre Nachricht gleich noch einmal.",
    ),
}


def failure_html(language: str | None) -> str:
    """Shown instead of an answer when the turn failed (after the silent retries): no technical details."""
    title, hint = _FAILURE_TEXT.get(language or "en", _FAILURE_TEXT["en"])
    return (
        '<div class="hp-failure" role="alert">'
        f'<p class="hp-failure__title">{html.escape(title)}</p>'
        f'<p class="hp-failure__hint">{html.escape(hint)}</p></div>'
    )


def decision_html(confirmed: int, cancelled: int) -> str:
    """The customer's side of a confirmation turn in the history (no free text was typed)."""
    parts = []
    if confirmed:
        parts.append(f"Confirmed {confirmed} change{'s' if confirmed != 1 else ''}")
    if cancelled:
        parts.append(f"Cancelled {cancelled} change{'s' if cancelled != 1 else ''}")
    return f'<p class="hp-decision">{html.escape(" · ".join(parts))}</p>'
