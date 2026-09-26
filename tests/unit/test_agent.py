"""Agent wiring without any Gemini call."""

from types import SimpleNamespace

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
    assert agent.model.model == "gemini-test"
    assert len(agent.tools) == 8
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
