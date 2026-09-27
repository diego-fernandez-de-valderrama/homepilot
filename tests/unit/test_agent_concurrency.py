"""The shared agent event loop: tools run off it, one turn or cart edit at a time per session, and a
confirmation retried after a failed turn never applies a cart change twice (scripted model, no Gemini)."""

import asyncio
import threading
from collections.abc import AsyncGenerator
from typing import cast

import pytest
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools import ToolContext

from smart_home_agent.agent import AgentService, build_agent
from smart_home_agent.agent.prompts import MEMORY_INSTRUCTION
from smart_home_agent.session import PROFILE_KEY
from smart_home_agent.tools import ThreadedFunctionTool
from tests.fakes import FakeProfileStore, FakeToolContext, services_for
from tests.unit.test_cart_agent import PRODUCTS
from tests.unit.test_guardrail_agent import ScriptedLlm, call_response, settings, text_response


class FailAfterToolLlm(ScriptedLlm):
    """Raises on the model call that follows the confirmed tool (quota or network error after retries)."""

    fail_on_request: int = 2

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if len(self.requests) + 1 == self.fail_on_request:
            self.requests.append(llm_request.model_copy(deep=True))
            raise ConnectionError("model unavailable")
        async for response in super().generate_content_async(llm_request, stream):
            yield response


def agent_service(llm: ScriptedLlm, store: FakeProfileStore | None = None) -> AgentService:
    services = services_for(PRODUCTS, profiles=store)
    agent = build_agent(services, settings(guardrail_output_check=False), None, model=llm)
    return AgentService(agent, "test-app", services.rich_content, services.cart, services.profile)


def test_retrying_a_confirmation_after_a_failed_turn_does_not_apply_it_twice():
    llm = FailAfterToolLlm(script=[call_response("add_to_cart", product_ids=["30173510"]), text_response("Done.")])
    agent = agent_service(llm)
    [confirmation] = agent.chat("s1", "Add the thermostat").pending_confirmations

    with pytest.raises(ConnectionError):
        agent.confirm("s1", {confirmation.request_id: True})
    assert [(i.product_id, i.quantity) for i in agent.state("s1").cart] == [("30173510", 1)]
    assert agent.applied_confirmations("s1", [confirmation.request_id]) == {confirmation.request_id}

    retry = agent.confirm("s1", {confirmation.request_id: True})
    assert retry.error == "already applied"
    assert [(i.product_id, i.quantity) for i in agent.state("s1").cart] == [("30173510", 1)]


def test_an_unanswered_confirmation_is_not_reported_as_applied():
    llm = ScriptedLlm(script=[call_response("add_to_cart", product_ids=["30173510"])])
    agent = agent_service(llm)
    [confirmation] = agent.chat("s1", "Add the thermostat").pending_confirmations
    assert agent.applied_confirmations("s1", [confirmation.request_id]) == set()


def test_sync_tools_run_off_the_event_loop_thread():
    threads: list[int] = []

    def probe() -> dict:
        """Records the thread it runs on."""
        threads.append(threading.get_ident())
        return {"status": "ok"}

    async def call() -> int:
        await ThreadedFunctionTool(probe).run_async(args={}, tool_context=cast(ToolContext, FakeToolContext()))
        return threading.get_ident()

    loop_thread = asyncio.run(call())
    assert threads and threads[0] != loop_thread


def test_a_cart_edit_waits_for_the_running_turn_of_the_same_session():
    agent = agent_service(ScriptedLlm(script=[call_response("add_to_cart", product_ids=["30173510"])]))
    [confirmation] = agent.chat("s1", "Add the thermostat").pending_confirmations
    agent.confirm("s1", {confirmation.request_id: True})

    async def scenario() -> tuple[bool, bool]:
        lock = agent._sessions.lock("s1", "customer")
        await lock.acquire()  # a turn of this session is running
        edit = asyncio.ensure_future(agent._customer_cart.set_quantity("s1", "30173510", 2, "customer"))
        await asyncio.sleep(0.05)
        waited = not edit.done()
        lock.release()
        await edit
        return waited, edit.done()

    waited, finished = agent._loop.submit(scenario()).result(timeout=5)
    assert waited and finished
    assert [(i.product_id, i.quantity) for i in agent.state("s1").cart] == [("30173510", 2)]


def test_memory_rules_stay_in_the_prompt_when_the_first_profile_load_fails():
    store = FakeProfileStore()
    store.fail = True
    llm = ScriptedLlm(script=[text_response("Hello!")])
    agent = agent_service(llm, store)
    agent.chat("s1", "Hi")
    assert MEMORY_INSTRUCTION.strip().splitlines()[0] in str(llm.requests[-1].config.system_instruction)
    assert agent._loop.run(agent._sessions.raw_state("s1", "customer"))[PROFILE_KEY] is None
