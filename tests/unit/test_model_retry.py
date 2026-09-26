"""Silent retries of empty model answers (no Gemini): the retry helper alone, then inside the real ADK runner."""

import asyncio
from collections.abc import AsyncIterator

from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

from smart_home_agent.agent.model import (
    RETRY_NOTE,
    ResilientGemini,
    backoff,
    http_retry_options,
    is_empty,
    retry_empty_responses,
)
from smart_home_agent.agent.orchestrator import AgentService, build_agent
from tests.fakes import FakeProfileStore, product, services_for
from tests.unit.test_guardrail_agent import settings

STOP = types.FinishReason.STOP


def empty() -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[]), finish_reason=STOP)


def text(value: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=value)]), finish_reason=STOP)


def call(name: str, **args: object) -> LlmResponse:
    function_call = types.FunctionCall(id=f"call-{name}", name=name, args=args)
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=function_call)]))


def request() -> LlmRequest:
    return LlmRequest(model="gemini-test", contents=[types.Content(role="user", parts=[types.Part(text="hi")])])


class Script:
    """Answers each call with the next response and records the requests it received."""

    def __init__(self, *responses: LlmResponse) -> None:
        self.responses = list(responses)
        self.request_sizes: list[int] = []  # number of contents each call received
        self.last_texts: list[str | None] = []  # text of the last content each call received

    async def __call__(self, llm_request: LlmRequest) -> AsyncIterator[LlmResponse]:
        self.request_sizes.append(len(llm_request.contents))
        self.last_texts.append(next(iter(llm_request.contents[-1].parts or []), types.Part()).text)
        llm_request.contents.append(types.Content(role="user", parts=[types.Part(text="added by the call")]))
        yield self.responses.pop(0)


def run(script: Script, retries: int = 3) -> tuple[list[LlmResponse], list[float]]:
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    async def collect() -> list[LlmResponse]:
        return [r async for r in retry_empty_responses(script, request(), retries, 1.0, 8.0, sleep)]

    return asyncio.run(collect()), sleeps


def test_what_counts_as_empty():
    assert is_empty(empty())
    assert is_empty(LlmResponse(content=None, finish_reason=STOP))
    thoughts_only = types.Content(role="model", parts=[types.Part(text="thinking...", thought=True)])
    assert is_empty(LlmResponse(content=thoughts_only, finish_reason=STOP))
    assert not is_empty(text("Hello"))
    assert not is_empty(call("view_cart"))
    assert not is_empty(LlmResponse(error_code="SAFETY", finish_reason=types.FinishReason.SAFETY))
    assert not is_empty(LlmResponse(content=None, partial=True))


def test_an_empty_answer_is_retried_silently():
    script = Script(empty(), empty(), text("Here you go"))
    responses, sleeps = run(script)
    assert [r.content.parts[0].text for r in responses if r.content and r.content.parts] == ["Here you go"]
    assert len(responses) == 1  # the empty answers never reach ADK
    assert sleeps == [1.0, 2.0]
    # Each retry starts from the original request (not from what the previous call added to it) plus the note:
    # an identical retry would get the same empty answer.
    assert script.request_sizes == [1, 2, 2]
    assert script.last_texts == ["hi", RETRY_NOTE, RETRY_NOTE]


def test_after_the_last_retry_the_empty_answer_is_passed_on():
    responses, sleeps = run(Script(empty(), empty(), empty(), empty(), empty()), retries=3)
    assert len(responses) == 1 and is_empty(responses[0])
    assert sleeps == [1.0, 2.0, 4.0]


def test_backoff_is_exponential_and_capped():
    assert [backoff(i, 1.0, 8.0) for i in range(6)] == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0]
    options = http_retry_options(3, 1.0, 8.0)
    assert (options.attempts, options.initial_delay, options.max_delay, options.exp_base) == (4, 1.0, 8.0, 2.0)


def test_agent_uses_the_retrying_model_with_the_configured_backoff():
    agent = build_agent(services_for([product("1")]), settings(model_retries=2, model_retry_initial_delay=0.5))
    model = agent.model
    assert isinstance(model, ResilientGemini)
    assert (model.empty_retries, model.retry_initial_delay, model.retry_max_delay) == (2, 0.5, 8.0)
    assert model.retry_options is not None and model.retry_options.attempts == 3


# ---------- Inside the ADK runner ----------


class ScriptedGemini(ResilientGemini):
    """The real retry path of ResilientGemini, with scripted answers instead of Gemini calls."""

    script: list[LlmResponse]
    calls: int = 0

    async def _generate_once(self, llm_request: LlmRequest) -> AsyncIterator[LlmResponse]:  # type: ignore[override]
        self.calls += 1
        yield self.script.pop(0) if self.script else empty()


def agent_with(model: ScriptedGemini, store: FakeProfileStore) -> AgentService:
    services = services_for([product("1")], profiles=store)
    agent = build_agent(services, settings(guardrail_output_check=False), None, model=model)
    return AgentService(agent, "test-app", services.rich_content, services.cart, services.profile)


def model(*script: LlmResponse, retries: int = 3) -> ScriptedGemini:
    return ScriptedGemini(model="gemini-test", script=list(script), empty_retries=retries, retry_initial_delay=0)


def test_empty_answer_after_a_tool_is_retried_without_running_the_tool_again():
    store = FakeProfileStore()
    llm = model(
        call("remember_customer_facts", evidence="I use HomeKit", ecosystems=["HomeKit"]), empty(), text("Noted!")
    )
    reply = agent_with(llm, store).chat("s1", "I use HomeKit", "anna")
    assert reply.text == "Noted!"
    assert reply.error is None and not reply.failed
    assert llm.calls == 3
    assert [f.value for f in store.facts] == ["apple_home"]  # the tool ran exactly once
    assert [c.name for c in reply.trace.tool_calls] == ["remember_customer_facts"]


def test_when_every_retry_is_empty_the_turn_is_reported_as_failed():
    llm = model(retries=2)
    reply = agent_with(llm, FakeProfileStore()).chat("s1", "Hello", "anna")
    assert llm.calls == 3
    assert reply.failed and reply.text == ""
    assert reply.error is not None and "no content" in reply.error


def test_the_retry_note_never_reaches_the_session():
    llm = model(empty(), text("Hello!"))
    service = agent_with(llm, FakeProfileStore())
    assert service.chat("s1", "Hi", "anna").text == "Hello!"
    session = service._run(service._sessions.get_session(app_name="test-app", user_id="anna", session_id="s1"))
    assert session is not None
    texts = [p.text for e in session.events if e.content for p in e.content.parts or [] if p.text]
    assert RETRY_NOTE not in texts and texts == ["Hi", "Hello!"]


def test_thinking_is_off_by_default_and_the_model_default_can_be_restored():
    config = build_agent(services_for([product("1")]), settings()).generate_content_config
    assert config is not None and config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0
    dynamic = build_agent(services_for([product("1")]), settings(thinking_budget=-1)).generate_content_config
    assert dynamic is not None and dynamic.thinking_config is None  # not sent: Gemini's dynamic default
