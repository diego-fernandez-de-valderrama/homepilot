"""Customer memory inside the agent (scripted model, fake store, no Gemini or database): the tool, the
instruction and the orchestrator, across conversations and customers."""

from types import SimpleNamespace

from google.adk.models import LlmResponse
from google.adk.tools import FunctionTool
from google.genai import types

from smart_home_agent.agent.orchestrator import AgentService, build_agent
from smart_home_agent.agent.prompts import build_instruction
from smart_home_agent.agent.state import PROFILE_KEY
from smart_home_agent.tools import build_tools
from tests.fakes import FakeProfileStore, FakeToolContext, product, services_for
from tests.unit.test_cart_agent import tool_responses
from tests.unit.test_guardrail_agent import ScriptedLlm, settings, text_response

PRODUCTS = [product("30173510", title="Acme Smart Radiator Thermostat", price=49.99)]


def memory_tool(store: FakeProfileStore):
    tools = {tool.name: tool.func for tool in build_tools(services_for(PRODUCTS, profiles=store))}
    return tools["remember_customer_facts"]


def service(llm: ScriptedLlm, store: FakeProfileStore) -> AgentService:
    services = services_for(PRODUCTS, profiles=store)
    agent = build_agent(services, settings(guardrail_output_check=False), None, model=llm)
    return AgentService(agent, "test-app", services.rich_content, services.cart, services.profile)


def remember_call(**args: object) -> LlmResponse:
    """Like `call_response`, whose own `name` parameter would clash with the tool's `name` argument."""
    call = types.FunctionCall(id="call-remember", name="remember_customer_facts", args=args)
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))


def system_instruction(llm: ScriptedLlm, index: int = -1) -> str:
    return str(llm.requests[index].config.system_instruction)


# ---------- Tool ----------


def test_memory_tool_only_exists_when_the_memory_is_enabled():
    assert "remember_customer_facts" not in {t.name for t in build_tools(services_for(PRODUCTS))}
    tool = FunctionTool(memory_tool(FakeProfileStore()))
    declaration = tool._get_declaration()
    assert declaration is not None
    properties = (declaration.parameters_json_schema or {}).get("properties", {})
    assert "evidence" in properties and "tool_context" not in properties
    assert not tool._require_confirmation


def test_memory_tool_stores_and_refreshes_the_turn_snapshot():
    store = FakeProfileStore()
    context = FakeToolContext(message="Hi, I'm Anna and I use HomeKit", user_id="anna")
    result = memory_tool(store)(context, "I'm Anna and I use HomeKit", name="Anna", ecosystems=["HomeKit"])
    assert result["status"] == "ok"
    assert result["added"] == ["name: Anna", "ecosystem: apple_home"]
    assert result["profile"] == ["name: Anna", "ecosystem: apple_home"]
    assert [f["value"] for f in context.state[PROFILE_KEY]["facts"]] == ["Anna", "apple_home"]
    assert {f.user_id for f in store.facts} == {"anna"}


def test_memory_tool_reports_rule_violations_as_invalid_input():
    store = FakeProfileStore()
    context = FakeToolContext(message="My friend has Alexa, what should I buy him?")
    result = memory_tool(store)(context, "My friend has Alexa", ecosystems=["Alexa"])
    assert result["status"] == "invalid_input" and "someone else" in result["message"]
    unquoted = memory_tool(store)(FakeToolContext(message="Add it to the cart"), "I own it", owned_devices=["x"])
    assert unquoted["status"] == "invalid_input"
    assert store.facts == [] and PROFILE_KEY not in context.state


def test_memory_tool_asks_for_clarification_on_ambiguous_terms():
    result = memory_tool(FakeProfileStore())(
        FakeToolContext(message="I use Google"), "I use Google", ecosystems=["Google"]
    )
    assert result["status"] == "needs_clarification" and result["options"]


# ---------- Instruction ----------


def test_instruction_has_no_memory_section_when_the_memory_is_disabled():
    text = build_instruction(SimpleNamespace(state={}))
    assert "remember_customer_facts" not in text and "(profile" not in text


def test_instruction_shows_the_rules_and_the_stored_profile():
    empty = build_instruction(SimpleNamespace(state={PROFILE_KEY: None}))
    assert "# Remembering the customer" in empty
    assert "they are not owned until the\n    customer says they own them" in empty
    assert "facts about other people" in empty
    assert "- nothing stored yet" in empty

    store = FakeProfileStore()
    memory_tool(store)(
        FakeToolContext(message="I use HomeKit", user_id="anna"), "I use HomeKit", ecosystems=["HomeKit"]
    )
    snapshot = store.load("anna").model_dump(mode="json")
    text = build_instruction(SimpleNamespace(state={PROFILE_KEY: snapshot}))
    assert '- ecosystem: apple_home ("HomeKit")' in text


# ---------- Orchestrator ----------


def test_memory_carries_over_to_a_new_conversation_of_the_same_customer_only():
    store = FakeProfileStore()
    llm = ScriptedLlm(
        script=[
            remember_call(evidence="I'm Anna, I use HomeKit", name="Anna", ecosystems=["HomeKit"]),
            text_response("Nice to meet you, Anna."),
            text_response("Welcome back, Anna."),
            text_response("Hello!"),
        ]
    )
    agent = service(llm, store)
    first = agent.chat("s1", "Hi, I'm Anna, I use HomeKit", "anna")
    assert first.text == "Nice to meet you, Anna."
    assert tool_responses(llm.requests[-1], "remember_customer_facts")[-1]["status"] == "ok"
    assert first.profile is not None and {f.value for f in first.profile.active()} == {"Anna", "apple_home"}
    assert "- nothing stored yet" in system_instruction(llm, 0)
    assert "- name: Anna" in system_instruction(llm, 1)  # the same turn already sees it

    agent.chat("s2", "Hello again", "anna")  # new conversation, same customer
    assert "- name: Anna" in system_instruction(llm)
    assert "- ecosystem: apple_home" in system_instruction(llm)

    other = agent.chat("s3", "Hello", "ben")
    assert "- nothing stored yet" in system_instruction(llm)
    assert other.profile is not None and other.profile.facts == []


def test_a_memory_failure_never_blocks_the_turn():
    store = FakeProfileStore()
    store.fail = True
    llm = ScriptedLlm(script=[text_response("Hi!")])
    reply = service(llm, store).chat("s1", "Hello", "anna")
    assert reply.text == "Hi!" and reply.profile is None


def test_profile_accessor_includes_retracted_facts():
    store = FakeProfileStore()
    tool = memory_tool(store)
    tool(FakeToolContext(message="I use Alexa", user_id="anna"), "I use Alexa", ecosystems=["Alexa"])
    tool(
        FakeToolContext(message="I stopped using Alexa", user_id="anna"),
        "I stopped using Alexa",
        no_longer_used=["Alexa"],
    )
    profile = service(ScriptedLlm(), store).profile("anna")
    assert profile is not None
    assert [(f.value, f.active) for f in profile.facts] == [("amazon_alexa", False)]
    assert (
        AgentService(build_agent(services_for(PRODUCTS), settings(), None, model=ScriptedLlm()), "t").profile() is None
    )
