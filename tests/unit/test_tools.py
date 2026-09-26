import pytest
from google.adk.tools import FunctionTool

from smart_home_agent.agent.state import STATE_KEY, read_state
from smart_home_agent.tools import build_tools
from tests.fakes import FakeToolContext, fact, product, requirement, services_for

PRODUCTS = [
    product("t1", price=55.0, facts=[fact("google_home"), fact("wifi")]),
    product("t2", price=120.0, facts=[fact("google_home"), fact("wifi"), fact("matter")]),
    product("t3", price=60.0, facts=[fact("google_assistant")]),
]


@pytest.fixture
def tools():
    return {tool.__name__: tool for tool in build_tools(services_for(PRODUCTS))}


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
    }
    for tool in tools.values():
        declaration = FunctionTool(tool)._get_declaration()
        properties = (declaration.parameters_json_schema or {}).get("properties", {})
        assert declaration.description
        assert "tool_context" not in properties  # injected by ADK, not visible to the model


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
    recommend = {t.__name__: t for t in build_tools(services_for([thermostat, hub]))}["recommend_products"]
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
