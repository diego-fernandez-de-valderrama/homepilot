"""Agent wiring without any Gemini call."""

from types import SimpleNamespace

import pytest
from google.adk.models import BaseLlm
from pydantic import SecretStr

from smart_home_agent.agent import AgentService, TurnTrace, build_agent
from smart_home_agent.agent.prompts import build_instruction
from smart_home_agent.config import AgentSettings, Settings
from smart_home_agent.session import STATE_KEY, TURN_LANGUAGE_KEY, detect_language
from tests.fakes import product, services_for


def _settings() -> Settings:
    from catalog_ingestion.core.settings import GeminiSettings, PostgresSettings, QdrantSettings

    return Settings(
        agent=AgentSettings(model="gemini-test"),
        gemini=GeminiSettings(api_key=SecretStr("test-key")),
        postgres=PostgresSettings(),
        qdrant=QdrantSettings(),
    )


def test_agent_builds_offline_with_all_tools():
    agent = build_agent(services_for([product("1")]), _settings())
    assert isinstance(agent.model, BaseLlm)
    assert agent.model.model == "gemini-test"
    assert len(agent.tools) == 11
    AgentService(agent, "test-app")  # runner + in-memory sessions, no network


def test_instruction_contains_rules_vocabulary_and_session():
    context = SimpleNamespace(
        state={STATE_KEY: {"budget_max": 150, "user_ecosystems": ["google_home"]}, TURN_LANGUAGE_KEY: "de"}
    )
    text = build_instruction(context)
    assert "Apple Siri is not Apple Home" in text
    assert "qualified" in text and "electrician" in text
    assert "google_home: Google Home" in text
    assert "budget_max: 150" in text
    assert "latest message is in German" in text
    assert "Every catalog product you mention must be shown through a tag" in text
    assert "otherwise, mention it with <item" in text
    assert "do not add\n    an <item/> for it" in text
    assert "The interface asks the customer to confirm every add and remove" in text


def test_instruction_frames_upselling_as_setup_completion():
    text = build_instruction(SimpleNamespace(state={}))
    assert "Upselling never means the most expensive product" in text
    for kind in ("- Required:", "- Optional:", "- Higher-value alternative:", "- Anything else is unnecessary"):
        assert kind in text
    assert "The budget covers the whole setup" in text
    assert "# Setup overview" in text and "# What else does it need" in text
    assert "The catalog lists no hub, gateway\nor subscription for it" in text
    assert "hub in one add_to_cart call" in text
    assert "Never add anything silently" in text


def test_instruction_keeps_the_cart_out_of_the_prompt():
    cart = {"cart": [{"product_id": "41234567", "quantity": 2}], "cart_checked": True}
    text = build_instruction(SimpleNamespace(state={STATE_KEY: cart}))
    assert "41234567" not in text
    assert "# Cart status" not in text
    changed = build_instruction(SimpleNamespace(state={STATE_KEY: {**cart, "cart_changed_by_user": True}}))
    assert "changed the cart in the interface" in changed
    assert "call view_cart once" in build_instruction(SimpleNamespace(state={}))


def test_instruction_without_state():
    text = build_instruction(SimpleNamespace(state={}))
    assert "nothing yet" in text
    assert "Reply language for this turn" not in text


def test_language_detection():
    assert detect_language("I need a thermostat compatible with Google Home") == "en"
    assert detect_language("Ich suche ein Thermostat für Google Home bis 150 €") == "de"
    assert detect_language("Und welches davon funktioniert auch mit Matter?") == "de"
    assert (
        detect_language("Compare 30173510 and 30387250") is None
        or detect_language("Compare 30173510 and 30387250") == "en"
    )
    assert detect_language("ok") is None


def test_trace_matches_calls_and_responses():
    trace = TurnTrace()
    trace.add_call("c1", "recommend_products", {"need": "thermostat"})
    trace.add_response(
        "c1",
        "recommend_products",
        {"status": "ok", "confirmed": [{"product": {"id": "1"}, "compatibility": "supported"}], "unconfirmed": []},
    )
    assert trace.intent == "recommendation"
    assert trace.tool_calls[0].status == "ok"
    assert trace.search_queries == [{"need": "thermostat"}]
    assert trace.compatibility == [{"product_id": "1", "overall": "supported", "group": "confirmed"}]
    assert TurnTrace().intent == "conversation (no tool used)"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Is the Fenster- und Türkontakt any good?", "en"),
        ("Is the Homematic IP Heizkörperthermostat compatible with Alexa?", "en"),
        ("Can I add the Heizkörperthermostat Evo to my cart?", "en"),
        ("I need a Matter smart plug.", "en"),
        ("I need a smart plug for Alexa.", "en"),
        ("I wannt a set of smart blindfolds for the 6 window sin my home", "en"),
        ("Hi, I'm Anna and at home I use Google Home.", "en"),
        ("nein danke", "de"),
        ("ja bitte", "de"),
        ("Welche Lampe ist gut für die Küche?", "de"),
        ("Mein Name ist Jürgen. Ich habe eine Philips Hue Bridge.", "de"),
        ("Ich habe Alexa.", "de"),
    ],
)
def test_language_is_not_decided_by_german_names(text, expected):
    assert detect_language(text) == expected


def test_greeting_with_a_german_name_is_not_german():
    # Without the name, "Hi, I am" is too little evidence for a decision.
    assert detect_language("Hi, I am Jürgen") != "de"
