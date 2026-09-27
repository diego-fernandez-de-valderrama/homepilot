from collections.abc import Callable
from typing import Any

import pytest
from google.adk.tools import FunctionTool

from smart_home_agent.agent.state import STATE_KEY, SessionState, read_state
from smart_home_agent.models.cart import CartItem
from smart_home_agent.tools import build_tools
from tests.fakes import FakeToolContext, fact, product, requirement, services_for

PRODUCTS = [
    product("t1", price=55.0, facts=[fact("google_home"), fact("wifi")]),
    product("t2", price=120.0, facts=[fact("google_home"), fact("wifi"), fact("matter")]),
    product("t3", price=60.0, facts=[fact("google_assistant")]),
]


def by_name(tools: list[FunctionTool]) -> dict[str, Callable[..., dict[str, Any]]]:
    return {tool.name: tool.func for tool in tools}


@pytest.fixture
def tools():
    return by_name(build_tools(services_for(PRODUCTS)))


def test_every_tool_has_a_valid_adk_declaration(tools):
    assert set(tools) == {
        "recommend_products",
        "search_products",
        "filter_products",
        "get_product",
        "check_compatibility",
        "compare_products",
        "get_evidence",
        "remember_preferences",
        "view_cart",
        "add_to_cart",
        "remove_from_cart",
    }
    for tool in tools.values():
        declaration = FunctionTool(tool)._get_declaration()
        assert declaration is not None
        properties = (declaration.parameters_json_schema or {}).get("properties", {})
        assert declaration.description
        assert "tool_context" not in properties  # injected by ADK, not visible to the model


def test_only_cart_changes_require_confirmation():
    confirmed = {tool.name for tool in build_tools(services_for(PRODUCTS)) if tool._require_confirmation}
    assert confirmed == {"add_to_cart", "remove_from_cart"}


def test_recommend_products_output_and_state(tools):
    context = FakeToolContext()
    result = tools["recommend_products"](
        "thermostat", context, category="Thermostat", max_price=150, must_support=["Google Home"]
    )
    assert result["status"] == "ok"
    assert result["best_match"] in {"t1", "t2"}
    assert {r["product"]["id"] for r in result["confirmed"]} == {"t1", "t2"}
    assert [r["product"]["id"] for r in result["unconfirmed"]] == ["t3"]
    session = read_state(context.state)
    assert session.current_category == "heating_control"
    assert result["best_match"] in session.selected_products
    assert set(session.candidate_products) == {"t1", "t2", "t3"}
    assert (session.last_upsell.model_dump(mode="json") if session.last_upsell else None) == result["upsell"]
    assert result["accessories"] == []


def test_recommended_accessories_are_known_to_the_session():
    hub = product("hub", title="Bosch Smart Home Controller II", category="hub_gateway", price=78.0)
    thermostat = product(
        "bosch", price=70.0, facts=[fact("google_home")], requirements=[requirement("bosch_smart_home_controller")]
    )
    recommend = by_name(build_tools(services_for([thermostat, hub])))["recommend_products"]
    context = FakeToolContext()
    result = recommend("thermostat", context, category="heating_control", must_support=["Google Home"])
    assert [a["product_id"] for a in result["accessories"]] == ["hub"]
    assert "hub" in read_state(context.state).candidate_products


def test_recommend_uses_session_preferences_as_defaults(tools):
    context = FakeToolContext()
    tools["remember_preferences"](context, ecosystems=["Google Home"], budget_max=100)
    result = tools["recommend_products"]("thermostat", context)
    assert result["applied_from_session"] == {"must_support": ["google_home"], "max_price": 100}
    assert [r["product"]["id"] for r in result["confirmed"]] == ["t1"]


def test_ambiguous_input_asks_for_clarification(tools):
    result = tools["recommend_products"]("thermostat", FakeToolContext(), must_support=["Google"])
    assert result["status"] == "needs_clarification"
    assert "Google Home" in result["options"]


def test_invalid_input_is_reported_not_raised(tools):
    result = tools["recommend_products"]("thermostat", FakeToolContext(), min_price=200, max_price=100)
    assert result["status"] == "invalid_input"
    assert tools["compare_products"](["t1"], FakeToolContext())["status"] == "invalid_input"
    assert tools["filter_products"](FakeToolContext(), sort="cheapest")["status"] == "invalid_input"


def test_get_product_and_not_found(tools):
    context = FakeToolContext()
    result = tools["get_product"]("t2", context)
    assert result["status"] == "ok"
    assert result["product"]["price"] == 120.0
    assert "provenance" not in result["product"]
    assert tools["get_product"]("404", context)["status"] == "not_found"


def test_check_compatibility_contract(tools):
    result = tools["check_compatibility"](["t1", "t3"], ["Google Home", "Matter"], FakeToolContext())
    assert result["status"] == "ok"
    by_id = {r["product_id"]: r for r in result["results"]}
    assert {c["term"]: c["status"] for c in by_id["t1"]["checks"]} == {"google_home": "supported", "matter": "unknown"}
    assert by_id["t3"]["overall"] == "unknown"
    assert tools["check_compatibility"](["404"], ["Matter"], FakeToolContext())["status"] == "not_found"


def test_check_compatibility_offers_the_required_hub_product():
    dimmer = product(
        "dimmer", price=68.0, facts=[fact("amazon_alexa")], requirements=[requirement("bosch_smart_home_controller")]
    )
    controller = product(
        "controller", title="Bosch Smart Home Controller II", category="hub_gateway", product_type="Hub", price=78.0
    )
    check = by_name(build_tools(services_for([dimmer, controller])))["check_compatibility"]
    [result] = check(["dimmer"], [], FakeToolContext())["results"]
    [accessory] = result["accessories"]
    assert (accessory["product_id"], accessory["status"], accessory["bundle_total"]) == (
        "controller",
        "unverified",
        146.0,
    )

    owned = check(["dimmer"], [], FakeToolContext(), owned_devices=["Bosch Smart Home Controller"])
    assert owned["results"][0]["accessories"] == []
    assert "requirements_note" not in result
    [plain] = check(["controller"], [], FakeToolContext())["results"]
    assert plain["accessories"] == []
    assert "lists no hub, gateway or subscription" in plain["requirements_note"]


def test_filter_products_contract(tools):
    context = FakeToolContext()
    result = tools["filter_products"](context, supports=["Matter"], max_price=150)
    assert result["status"] == "ok"
    assert result["total"] == 1
    assert [p["id"] for p in result["products"]] == ["t2"]


def test_compare_products_updates_state(tools):
    context = FakeToolContext()
    result = tools["compare_products"](["t1", "t2"], context)
    assert result["status"] == "ok"
    assert read_state(context.state).comparison_products == ["t1", "t2"]


def test_get_evidence_contract(tools):
    assert tools["get_evidence"]("t1", "Google Home")["items"][0]["source"] == "catalog"
    unknown = tools["get_evidence"]("t1", "Matter")
    assert unknown["items"] == [] and "unknown" in unknown["note"]
    assert tools["get_evidence"]("t1", "Teletubby")["status"] == "unrecognized"


def test_remember_preferences_classifies_by_dimension(tools):
    context = FakeToolContext()
    result = tools["remember_preferences"](
        context, language="DE", ecosystems=["HomeKit", "Alexa", "Zigbee"], owned_devices=["Hue Bridge"]
    )
    assert result["status"] == "ok"
    session = read_state(context.state)
    assert session.language == "de"
    assert session.user_ecosystems == ["apple_home", "amazon_alexa"]
    assert session.user_protocols == ["zigbee"]
    assert session.owned_devices == ["philips_hue_bridge"]
    assert STATE_KEY in context.state


def cart_context(*pairs: tuple[str, int], changed: bool = False) -> FakeToolContext:
    session = SessionState(
        cart=[CartItem(product_id=pid, quantity=q) for pid, q in pairs], cart_changed_by_user=changed
    )
    return FakeToolContext({STATE_KEY: session.model_dump(mode="json")})


def test_view_cart_syncs_the_flags(tools):
    context = cart_context(("t1", 2), changed=True)
    result = tools["view_cart"](context)
    assert result["status"] == "ok"
    assert result["item_count"] == 2 and result["cart_total"] == 110.0
    assert result["items"][0]["title"] == "Product t1"
    session = read_state(context.state)
    assert session.cart_checked and not session.cart_changed_by_user
    assert tools["view_cart"](cart_context())["note"] == "the cart is empty"


def by_product(result: dict) -> dict[str, dict]:
    return {change["product_id"]: change for change in result["changes"]}


def test_add_to_cart_reports_what_is_left(tools):
    context = cart_context(("t2", 1))
    result = tools["add_to_cart"](["t1"], context, quantities=[2])
    assert (result["status"], result["action"]) == ("ok", "add")
    change = by_product(result)["t1"]
    assert (change["quantity_changed"], change["remaining_of_product"]) == (2, 2)
    assert change["title"] == "Product t1" and "note" not in change
    assert [(i["product_id"], i["quantity"]) for i in result["remaining_items"]] == [("t2", 1), ("t1", 2)]
    assert "note" not in result
    assert read_state(context.state).cart_checked


def test_add_several_products_in_one_change(tools):
    context = cart_context(("t1", 1))
    result = tools["add_to_cart"](["t1", "t2", "t3"], context, quantities=[1, 2, 1])
    assert result["status"] == "ok"
    changes = by_product(result)
    assert {pid: (c["quantity_changed"], c["remaining_of_product"]) for pid, c in changes.items()} == {
        "t1": (1, 2),
        "t2": (2, 2),
        "t3": (1, 1),
    }
    assert result["cart_total"] == 2 * 55.0 + 2 * 120.0 + 60.0
    default = tools["add_to_cart"](["t3", "t3"], cart_context())  # no quantities: 1 each, repeats merged
    assert by_product(default)["t3"]["remaining_of_product"] == 2


def test_remove_from_cart_partial_and_complete(tools):
    context = cart_context(("t1", 3), ("t2", 1))
    partial = by_product(tools["remove_from_cart"](["t1"], context, quantities=[1]))["t1"]
    assert (partial["quantity_changed"], partial["remaining_of_product"]) == (1, 2)
    complete = tools["remove_from_cart"](["t1"], context)
    assert (by_product(complete)["t1"]["quantity_changed"], by_product(complete)["t1"]["remaining_of_product"]) == (
        2,
        0,
    )
    assert by_product(complete)["t1"]["note"] == "none of this product left in the cart"
    assert [i["product_id"] for i in complete["remaining_items"]] == ["t2"]
    last = tools["remove_from_cart"](["t2"], context)
    assert last["remaining_items"] == [] and last["note"] == "the cart is empty"


def test_remove_several_products_with_zero_meaning_all(tools):
    context = cart_context(("t1", 3), ("t2", 2), ("t3", 1))
    result = tools["remove_from_cart"](["t1", "t2"], context, quantities=[1, 0])
    assert result["status"] == "ok"
    assert {pid: c["remaining_of_product"] for pid, c in by_product(result).items()} == {"t1": 2, "t2": 0}
    assert [(i["product_id"], i["quantity"]) for i in result["remaining_items"]] == [("t1", 2), ("t3", 1)]


def test_a_change_is_all_or_nothing(tools):
    context = cart_context(("t1", 1))
    unknown = tools["add_to_cart"](["t2", "404"], context)
    assert unknown["status"] == "not_found"
    assert unknown["errors"] == [{"product_id": "404", "status": "not_found", "message": "not in the catalog"}]
    assert {pid: c["quantity_changed"] for pid, c in by_product(unknown).items()} == {"t2": 0, "404": 0}
    assert "Nothing was changed" in unknown["message"]
    missing = tools["remove_from_cart"](["t1", "t2"], context)
    assert missing["status"] == "invalid_input" and missing["errors"][0]["product_id"] == "t2"
    assert by_product(missing)["t1"]["remaining_of_product"] == 1
    assert [i["product_id"] for i in missing["remaining_items"]] == ["t1"]
    for bad in (
        tools["add_to_cart"](["t1"], context, quantities=[500]),
        tools["add_to_cart"](["t1", "t2"], context, quantities=[1]),
        tools["add_to_cart"]([], context),
    ):
        assert bad["status"] == "invalid_input"
    assert read_state(context.state).cart == [CartItem(product_id="t1", quantity=1)]


def test_data_errors_are_not_reported_as_invalid_input():
    from pydantic import BaseModel

    from smart_home_agent.tools._common import tool_errors

    class Stored(BaseModel):
        price: float

    @tool_errors
    def broken() -> dict:
        Stored.model_validate({"price": "not a number"})  # corrupt stored document, not the tool's arguments
        return {"status": "ok"}

    result = broken()
    assert result["status"] == "error" and "could not be completed" in result["message"]
