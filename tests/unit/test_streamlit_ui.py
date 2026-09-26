from pathlib import Path

from catalog_ingestion.domain.enums import FactStatus
from streamlit.testing.v1 import AppTest

from smart_home_agent.agent.state import SessionState
from smart_home_agent.models.cart import CartChangeLine, CartConfirmation, CartItem
from smart_home_agent.services.cart import CartService
from smart_home_agent.services.comparison import compare
from smart_home_agent.services.rich_content import product_compatibility
from smart_home_agent.ui import streamlit_app
from smart_home_agent.ui.components import (
    Suggestion,
    answer_markdown,
    cart_confirmation_html,
    cart_header_html,
    cart_line_html,
    cart_total_html,
    comparison_html,
    compatibility_html,
    confirm_button_label,
    item_chip_html,
    masthead_html,
    product_cards_html,
    setup_panel_html,
    suggestion_tile_html,
    tool_progress_html,
    tool_status_label,
    upgrade_html,
)
from tests.fakes import FakeCatalog, fact, product
from tests.unit.test_rich import BASIC, PRO, UPSELL

APP = Path(streamlit_app.__file__)


def test_empty_state_renders_without_backend():
    app = AppTest.from_file(str(APP)).run()  # the agent service is only built when a prompt arrives
    assert not app.exception
    labels = [button.label for button in app.button]
    assert "New conversation" in labels
    assert all(s.title in labels for s in streamlit_app.SUGGESTIONS)
    assert [toggle.label for toggle in app.toggle] == ["Developer panel"]


def test_setup_panel_without_known_facts_invites_the_user():
    assert "Tell me about your setup" in setup_panel_html(None)
    assert "Tell me about your setup" in setup_panel_html(SessionState())


def test_setup_panel_shows_only_known_facts_with_labels():
    state = SessionState(language="de", user_ecosystems=["apple_home"], owned_devices=[], budget_max=150)
    panel = setup_panel_html(state)
    assert "Apple Home" in panel
    assert "up to 150 €" in panel
    assert "None" in panel  # the user said they own no hub
    assert "Deutsch" in panel
    assert "Looking at" not in panel


def test_dynamic_values_are_escaped():
    panel = setup_panel_html(SessionState(requirements=["<script>x</script>"]))
    assert "<script>" not in panel
    tile = suggestion_tile_html(Suggestion("home", "Topic", "<b>Title</b>", "Say <hi>"))
    assert "<b>" not in tile and "&lt;hi&gt;" in tile


def test_progress_labels_name_the_tool_actually_called():
    assert tool_status_label("compare_products") == "Comparing products"
    assert tool_status_label("some_new_tool") == "Working on your request"
    assert "Checking compatibility" in tool_progress_html(tool_status_label("check_compatibility"))


def test_product_cards_escape_and_only_link_http_urls():
    plug = product("30000009", title="<b>Plug</b>", price=19.9).model_copy(update={"source_url": "javascript:x"})
    card = product_cards_html([plug])
    assert "&lt;b&gt;Plug&lt;/b&gt;" in card and "<b>" not in card
    assert "19.90 €" in card
    assert "javascript:" not in card and "View in shop" not in card


def test_inline_item_is_a_chip_with_a_hover_card_from_catalog_data():
    plug = product("30000009", title="Plug *Pro* <b>", price=19.9, brand="Innr").model_copy(
        update={"source_url": "https://www.bauhaus.info/p/30000009", "image_url": "https://cdn.example/p.webp"}
    )
    chip = item_chip_html(plug, plug.id)
    assert chip.startswith('<span class="hp-item" tabindex="0">')
    assert "Plug \\*Pro\\* &lt;b&gt;" in chip and "<b>" not in chip  # escaped for HTML and markdown
    assert '<span class="hp-item__price">19.90 €</span>' in chip
    assert 'class="hp-item__card" role="tooltip"' in chip
    assert 'src="https://cdn.example/p.webp"' in chip and 'href="https://www.bauhaus.info/p/30000009"' in chip
    assert "\n" not in chip  # stays inline inside the sentence
    assert item_chip_html(None, "30000009") == "30000009"


def test_chip_hover_card_uses_the_placeholder_for_a_gone_image():
    plug = product("30000009").model_copy(update={"image_url": "https://cdn.example/gone.webp"})
    chip = item_chip_html(plug, plug.id, missing_images=frozenset({"https://cdn.example/gone.webp"}))
    assert "gone.webp" not in chip and "No image" in chip


def test_answer_markdown_escapes_model_html_and_drops_echoed_titles():
    plug = product("30000009", title="Philips Hue Bewegungsmelder", price=39.65)
    body = 'The <item id="30000009"/> Philips Hue Bewegungsmelder works. <script>x</script> **bold**'
    markdown = answer_markdown(body, {plug.id: plug})
    assert markdown.count("Philips Hue Bewegungsmelder") == 2  # chip name + hover card title, no echo
    assert "&lt;script>" in markdown and "<script>" not in markdown
    assert "**bold**" in markdown  # the model's markdown still works


def test_compatibility_component_shows_unknown_as_not_confirmed():
    html = compatibility_html(PRO, product_compatibility(PRO, ["google_home", "apple_home"], None))
    assert "Not confirmed for your setup" in html
    assert "hp-compat-chip--unknown" in html and "Not confirmed" in html
    assert "Works with your setup" not in html


def test_compatibility_component_with_explicit_negative_evidence():
    plug = product("30000009", facts=[fact("apple_home", FactStatus.UNSUPPORTED)])
    html = compatibility_html(plug, product_compatibility(plug, ["apple_home"], None))
    assert "Not compatible with your setup" in html and "Not supported" in html


def test_comparison_never_shows_unknown_as_supported():
    html = comparison_html(compare([BASIC, PRO]))
    assert "Acme Basic Thermostat" in html and "Acme Pro Thermostat" in html
    assert "hp-compare__status--unknown" in html  # Apple Home: listed for PRO only, unknown for BASIC
    assert "data completeness" not in html


def test_upgrade_component_uses_the_upsell_data():
    html = upgrade_html(BASIC, PRO, UPSELL)
    assert "+30.00 €" in html and "Also supports Matter" in html
    assert html.index("Acme Basic Thermostat") < html.index("Acme Pro Thermostat")


def _render_tagged_answer() -> None:
    from smart_home_agent.services.rich_content import RichContentService
    from smart_home_agent.ui.streamlit_app import render_answer
    from tests.fakes import FakeCatalog
    from tests.unit.test_rich import ANSWER, BASIC, PRO, UPSELL

    content = RichContentService(FakeCatalog([BASIC, PRO])).resolve(ANSWER, ["google_home"], None, UPSELL)
    render_answer(ANSWER, content)
    render_answer('Unresolved: <item id="39999999"/>\n<items ids="39999999"/>', None)


def test_render_answer_turns_tags_into_components():
    app = AppTest.from_function(_render_tagged_answer).run()
    assert not app.exception
    markdown = "\n".join(m.value for m in app.markdown)
    assert "<item " not in markdown and "<items" not in markdown
    assert '<span class="hp-item__name">Acme Basic Thermostat</span>' in markdown
    assert "hp-item__price" not in markdown  # also in the <items> block: the chip does not repeat the price
    assert "Unresolved: 39999999" in markdown


def test_cards_show_a_placeholder_for_images_known_to_be_gone():
    url = "https://media.cdn.example/m/1/prod.webp"
    plug = product("30000009").model_copy(update={"image_url": url})
    assert f'src="{url}"' in product_cards_html([plug])
    card = product_cards_html([plug], frozenset({url}))
    assert url not in card and "No image" in card


def test_inline_item_for_a_product_already_in_a_block_does_not_repeat_the_price():
    plug = product("30000009", title="Plug", price=19.9)
    chip = item_chip_html(plug, plug.id, shown_in_block=True)
    assert "hp-item__price" not in chip and '<span class="hp-item__card-price">19.90 €</span>' in chip


def test_stylesheet_has_no_markup():
    # st.html sanitizes its input: markup-like text such as "<item/>" (even in a CSS comment) drops the whole
    # <style> block, and the page renders unstyled.
    css = (APP.parent / "styles.css").read_text(encoding="utf-8")
    assert "<" not in css


def test_hover_card_flip_script_and_styles_agree():
    script = (APP.parent / "item_card.js").read_text(encoding="utf-8")
    css = (APP.parent / "styles.css").read_text(encoding="utf-8")
    assert '"hp-item--below"' in script and ".hp-item--below .hp-item__card" in css
    assert ".hp-masthead" in script  # room is measured below the pinned masthead, not the window top
    assert "</script" not in script  # embedded in a <script> tag by inject_behaviour


CART = CartService(FakeCatalog([product("a", title="<b>Thermo</b>", price=19.99), product("n", price=None)]))


def test_cart_panel_states():
    empty = CART.view([])
    assert "Your cart is empty" in cart_header_html(empty)
    view = CART.view([CartItem(product_id="a", quantity=2), CartItem(product_id="gone", quantity=1)])
    assert "hp-cart__count" in cart_header_html(view) and ">3<" in cart_header_html(view)
    line = cart_line_html(view.lines[0])
    assert "<b>" not in line and "&lt;b&gt;Thermo" in line
    assert "39.98 €" in line and "2 × 19.99 €" in line
    assert "No longer available" in cart_line_html(view.lines[1])
    # Without an image: a decorative package glyph instead of placeholder text.
    assert "hp-thumb-glyph" in line and "No image" not in line
    assert "hp-thumb-glyph" in cart_line_html(view.lines[1])
    assert "39.98 €" in cart_total_html(view)
    assert "not listed" in cart_total_html(CART.view([CartItem(product_id="n", quantity=1)]))


def test_masthead_badge_counts_units():
    assert ">0<" in masthead_html() and "hp-cart-badge--filled" not in masthead_html()
    assert "hp-cart-badge--filled" in masthead_html(3) and "3 items in your cart" in masthead_html(3)
    assert "1 item in your cart" in masthead_html(1)


def test_confirmation_card_from_catalog_data():
    add = CART.describe("r1", "add", {"product_ids": ["a"], "quantities": [2]}, [])
    card = cart_confirmation_html(add)
    assert "Add to cart" in card and "&lt;b&gt;Thermo" in card and "products" not in card
    assert "2 × 19.99 € = 39.98 €" in card and "after this change: 2" in card
    assert "hp-confirm__total" not in card  # a single product needs no change total
    assert "hp-confirm__state" not in card  # open: the buttons are rendered below it
    assert confirm_button_label(add) == "Add to cart"
    assert "Added to your cart" in cart_confirmation_html(add, "confirmed")
    assert "Not added" in cart_confirmation_html(add, "cancelled")
    assert "Not confirmed" in cart_confirmation_html(add, "expired")
    remove_all = CART.describe("r2", "remove", {"product_ids": ["a"]}, [CartItem(product_id="a", quantity=3)])
    removal = cart_confirmation_html(remove_all)
    assert "Remove from cart" in removal and "All 3" in removal and "after this change: 0" in removal
    unknown = CartConfirmation(
        request_id="r3",
        action="add",
        lines=[CartChangeLine(product_id="99", quantity=1, product=None)],
    )
    assert "not in the catalog" in cart_confirmation_html(unknown)


def test_confirmation_card_for_several_products():
    batch = CART.describe("r1", "add", {"product_ids": ["a", "n"], "quantities": [2, 1]}, [])
    card = cart_confirmation_html(batch)
    assert "Add to cart · 2 products" in card
    assert card.count('class="hp-confirm__body"') == 2
    assert "hp-confirm__total" not in card  # one product has no listed price: no misleading total
    priced = CART.describe("r2", "add", {"product_ids": ["a", "a"], "quantities": [1, 1]}, [])
    assert len(priced.lines) == 1  # repeats are merged into one line
    two = CartConfirmation(
        request_id="r3",
        action="remove",
        lines=[
            CartChangeLine(product_id="a", quantity=None, product=product("a", price=19.99), in_cart=2),
            CartChangeLine(product_id="b", quantity=1, product=product("b", price=5.0), in_cart=1),
        ],
    )
    removal = cart_confirmation_html(two)
    assert "−44.98 €" in removal and "Change total" in removal
    assert confirm_button_label(two) == "Remove 2 products" and confirm_button_label(batch) == "Add 2 products"


def _confirmation_script(decided: bool) -> None:
    import streamlit as st

    from smart_home_agent.models.cart import CartChangeLine, CartConfirmation
    from smart_home_agent.ui.streamlit_app import render_confirmations

    st.session_state.setdefault("expired", set())
    st.session_state.setdefault("decisions", {"r1": True} if decided else {})
    line = CartChangeLine(product_id="a", quantity=1, product=None)
    change = CartConfirmation(request_id="r1", action="add", lines=[line])
    render_confirmations([change], interactive=True)


def _slot_keys(app: AppTest) -> tuple[list[int], list[int]]:
    """Positions of the top-level slots and of the slots inside the card container."""
    top = sorted(app.main.children)
    card = app.main.children[top[-1]]
    return top, sorted(card.children)


def test_deciding_a_change_keeps_every_element_in_place():
    """Regression: the lead line and the buttons disappeared on click, the card moved up one slot and the
    previous run's card stayed visible as a faded duplicate while the confirmation turn ran."""
    open_app = AppTest.from_function(_confirmation_script, args=(False,)).run()
    decided_app = AppTest.from_function(_confirmation_script, args=(True,)).run()
    assert not open_app.exception and not decided_app.exception
    assert [b.label for b in open_app.button] == ["Add to cart", "Cancel"]
    assert list(decided_app.button) == []
    assert _slot_keys(open_app) == _slot_keys(decided_app)
