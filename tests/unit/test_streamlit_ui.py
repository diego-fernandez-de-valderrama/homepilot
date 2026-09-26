from pathlib import Path

import pytest
import streamlit as st
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


def test_masthead_is_brand_only():
    # The cart button is a Streamlit widget beside the masthead (it opens the customer panel), not HTML.
    masthead = masthead_html()
    assert "hp-masthead" in masthead and "HomePilot" in masthead
    assert "cart" not in masthead


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


@pytest.fixture
def memory_off(monkeypatch):
    """Picker tests without the real memory database: no stored customers, only this session's."""
    monkeypatch.setenv("AGENT_MEMORY_ENABLED", "false")
    st.cache_resource.clear()
    st.cache_data.clear()
    yield
    st.cache_resource.clear()
    st.cache_data.clear()


def picker_app() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=15).run()


def new_customer(app: AppTest, customer_id: str) -> None:
    app.selectbox(key="hp-customer-pick").set_value(streamlit_app.NEW_CUSTOMER).run()
    app.text_input(key="hp-customer-new").set_value(customer_id).run()


def test_new_customer_is_created_selected_and_starts_a_new_conversation(memory_off):
    app = picker_app()
    picker = app.selectbox(key="hp-customer-pick")
    assert picker.value == "customer" and picker.options == ["customer", "+ New customer…"]
    assert any("not available" in c.value for c in app.caption)
    first_session = app.session_state["session_id"]
    app.session_state["messages"] = [{"role": "user", "content": "I use HomeKit"}]
    new_customer(app, "  anna ")
    assert not app.exception
    assert app.session_state["customer_id"] == "anna"
    assert app.selectbox(key="hp-customer-pick").value == "anna"
    assert app.session_state["session_id"] != first_session and app.session_state["messages"] == []
    assert not app.text_input  # the id field closes once the customer is created


def test_picking_an_earlier_customer_switches_back(memory_off):
    app = picker_app()
    new_customer(app, "anna")
    session = app.session_state["session_id"]
    assert app.selectbox(key="hp-customer-pick").options == ["customer", "anna", "+ New customer…"]
    app.selectbox(key="hp-customer-pick").set_value("customer").run()
    assert not app.exception
    assert app.session_state["customer_id"] == "customer"
    assert app.session_state["session_id"] != session


def test_new_conversation_keeps_the_customer(memory_off):
    app = picker_app()
    new_customer(app, "anna")
    session = app.session_state["session_id"]
    next(b for b in app.button if b.label == "New conversation").click().run()
    assert not app.exception
    assert app.session_state["customer_id"] == "anna"
    assert app.selectbox(key="hp-customer-pick").value == "anna"
    assert app.session_state["session_id"] != session


def test_picker_lists_stored_customers_most_recent_first_with_fact_counts():
    from datetime import UTC, datetime

    from smart_home_agent.models.profile import CustomerSummary

    stored = [
        CustomerSummary(user_id="ben", active_facts=1, total_facts=1, last_activity=datetime(2026, 9, 26, tzinfo=UTC)),
        CustomerSummary(user_id="anna", active_facts=3, total_facts=4, last_activity=datetime(2026, 9, 25, tzinfo=UTC)),
        CustomerSummary(user_id="old", active_facts=0, total_facts=2, last_activity=datetime(2026, 9, 1, tzinfo=UTC)),
    ]
    options = streamlit_app.customer_options(stored, "customer", ["anna", "clara"])
    assert options == ["ben", "anna", "old", "clara", "customer", streamlit_app.NEW_CUSTOMER]
    assert [streamlit_app.customer_label(o) for o in options] == [
        "ben",
        "anna",
        "old",
        "clara",
        "customer",
        "+ New customer…",
    ]
    assert streamlit_app.customer_options(None, "customer", []) == ["customer", streamlit_app.NEW_CUSTOMER]
    # The fact count is shown under the picker, never in the option labels.
    assert streamlit_app.stored_facts_caption("anna", stored) == "3 facts stored for this customer."
    assert streamlit_app.stored_facts_caption("ben", stored) == "1 fact stored for this customer."
    assert streamlit_app.stored_facts_caption("old", stored) == "Nothing stored for this customer yet."
    assert streamlit_app.stored_facts_caption("x", None).startswith("Stored customers are not available")


class _State(dict):
    """Stand-in for st.session_state (item and attribute access)."""

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def test_a_stale_value_from_the_browser_never_becomes_a_customer(monkeypatch):
    """Regression: labels used to carry the fact count ("anna · 1 fact"). Streamlit's browser side keeps a
    selectbox value as its label, so after a new fact it sent the old label back; Streamlit passes an unknown
    label through as a raw value, and the picker switched to a customer literally named "anna · 1 fact".
    (AppTest cannot send a value outside the options, so the callback is called directly.)"""
    state = _State(
        {
            "customer_id": "anna",
            "known_customers": ["anna"],
            "session_id": "s1",
            "hp-customer-options": ["anna", "ben", streamlit_app.NEW_CUSTOMER],
            "hp-customer-pick": "anna · 1 fact",
        }
    )
    monkeypatch.setattr(streamlit_app.st, "session_state", state)
    streamlit_app.pick_customer()
    assert state["customer_id"] == "anna" and state["hp-customer-pick"] == "anna"
    assert state["session_id"] == "s1" and state["known_customers"] == ["anna"]  # no switch, no new conversation

    state["hp-customer-pick"] = "ben"  # a real option still switches
    streamlit_app.pick_customer()
    assert state["customer_id"] == "ben" and state["session_id"] != "s1"


def test_stored_data_button_only_in_developer_mode():
    app = AppTest.from_file(str(APP)).run()
    assert "Stored data about me" not in [b.label for b in app.button]
    app.toggle(key="hp-debug").set_value(True).run()
    assert "Stored data about me" in [b.label for b in app.button]


def _customer_memory_dialog() -> None:
    from smart_home_agent.services.profile import ProfileService
    from smart_home_agent.ui import streamlit_app as app
    from tests.fakes import FakeProfileStore

    service = ProfileService(FakeProfileStore())
    service.remember("anna", "s1", "I use Alexa", "I use Alexa", ecosystems=["Alexa"])
    service.remember("anna", "s2", "I sold my Hue Bridge", "I sold my Hue Bridge", owned_devices=["Hue Bridge"])
    service.remember("anna", "s2", "I sold my Hue Bridge", "I sold my Hue Bridge", no_longer_owned=["Hue Bridge"])

    class Agent:  # stands in for AgentService (no Gemini, no database)
        def profile(self, user_id: str, include_retracted: bool = True):
            return service.profile(user_id, include_retracted)

    setattr(app, "get_agent_service", Agent)  # noqa: B010 (a plain assignment does not type-check)
    app.show_customer_memory("anna")


def test_customer_memory_dialog_lists_active_and_retracted_facts():
    app = AppTest.from_function(_customer_memory_dialog).run()
    assert not app.exception
    assert any("`anna` · 1 active, 2 total facts" in m.value for m in app.markdown)
    [table] = app.dataframe
    rows = table.value.to_dict("records")
    assert [(r["kind"], r["value"], r["active"]) for r in rows] == [
        ("ecosystem", "amazon_alexa", True),
        ("owned_device", "philips_hue_bridge", False),
    ]
    assert rows[1]["retracted because"] == "I sold my Hue Bridge"


def test_failure_notice_is_friendly_and_localized():
    from smart_home_agent.ui.components import failure_html

    english = failure_html("en")
    assert "Sorry, I couldn&#x27;t finish my answer." in english and 'role="alert"' in english
    assert "Entschuldigung" in failure_html("de")
    assert failure_html(None) == english
    assert "Error" not in english and "finish_reason" not in english  # no technical details for customers


def _failed_turn_in_history() -> None:
    import streamlit as st

    from smart_home_agent.agent.state import SessionState
    from smart_home_agent.agent.trace import AgentReply, TurnTrace
    from smart_home_agent.ui.streamlit_app import render_message

    reply = AgentReply(
        text="", detected_language="de", trace=TurnTrace(), state=SessionState(), error="The model returned no content"
    )
    message = {"role": "assistant", "content": "", "reply": reply, "failed": True, "language": "de"}
    render_message(message, debug=bool(st.query_params.get("debug")))


def test_failed_turn_shows_the_notice_and_the_detail_only_to_developers():
    app = AppTest.from_function(_failed_turn_in_history).run()
    assert not app.exception
    assert any("Entschuldigung" in str(h.proto) for h in app.get("html"))
    assert not any("no content" in c.value for c in app.caption)
    app.query_params["debug"] = "1"
    app.run()
    assert any("Developer detail: The model returned no content" in c.value for c in app.caption)
