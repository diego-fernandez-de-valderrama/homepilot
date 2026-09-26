"""Agent wiring without any Gemini call."""

from types import SimpleNamespace

from google.adk.models import BaseLlm
from pydantic import SecretStr

from smart_home_agent.agent.language import detect_language
from smart_home_agent.agent.orchestrator import AgentService, build_agent
from smart_home_agent.agent.prompts import build_instruction
from smart_home_agent.agent.state import STATE_KEY, TURN_LANGUAGE_KEY
from smart_home_agent.agent.trace import TurnTrace
from smart_home_agent.config import AgentSettings, Settings
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
