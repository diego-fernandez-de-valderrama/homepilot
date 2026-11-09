"""The cart tools inside the real ADK runner with a scripted model (no Gemini): every add/remove waits for the
customer's confirmation, and the model always learns the outcome and what is left in the cart."""

from types import SimpleNamespace
from typing import Any

from google.adk.models import LlmRequest

from smart_home_agent.agent import AgentService, build_agent
from smart_home_agent.agent.prompts import build_instruction
from tests.fakes import product, services_for
from tests.unit.test_guardrail_agent import ScriptedLlm, call_response, settings, text_response

PRODUCTS = [
    product("30173510", title="Acme Smart Radiator Thermostat", price=49.99),
    product("30387250", title="Acme Bridge", product_type="Smart home bridge", price=59.0),
]


def service(llm: ScriptedLlm) -> AgentService:
    services = services_for(PRODUCTS)
    agent = build_agent(services, settings(guardrail_output_check=False), None, model=llm)
    return AgentService(agent, "test-app", services.rich_content, services.cart)


def tool_responses(request: LlmRequest, name: str) -> list[dict[str, Any]]:
    return [
        dict(part.function_response.response or {})
        for content in request.contents
        for part in content.parts or []
        if part.function_response and part.function_response.name == name
    ]


def test_add_waits_for_confirmation_and_then_runs():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30173510"], quantities=[2]),
            text_response("Done, it is in your cart."),
        ]
    )
    agent = service(llm)
    pending = agent.chat("s1", "Add two of the Acme thermostat to my cart")
    assert pending.text == ""
    assert len(llm.requests) == 1  # the turn stops at the confirmation, no second model call
    [confirmation] = pending.pending_confirmations
    [line] = confirmation.lines
    assert (confirmation.action, line.product_id, line.quantity) == ("add", "30173510", 2)
    assert line.product is not None and line.product.title == "Acme Smart Radiator Thermostat"
    assert agent.state("s1").cart == []

    reply = agent.confirm("s1", {confirmation.request_id: True})
    assert reply.text == "Done, it is in your cart."
    assert reply.pending_confirmations == []
    assert [(i.product_id, i.quantity) for i in agent.state("s1").cart] == [("30173510", 2)]
    [result] = tool_responses(llm.requests[-1], "add_to_cart")[-1:]
    assert result["status"] == "ok"
    assert result["changes"][0]["remaining_of_product"] == 2
    assert [i["product_id"] for i in result["remaining_items"]] == ["30173510"]
    view = agent.cart("s1")
    assert (view.item_count, view.total) == (2, 99.98)


def test_rejected_change_reports_the_unchanged_cart():
    llm = ScriptedLlm(
        script=[call_response("add_to_cart", product_ids=["30173510"]), text_response("OK, I left it out.")]
    )
    agent = service(llm)
    [confirmation] = agent.chat("s1", "Put the thermostat in the cart").pending_confirmations
    reply = agent.confirm("s1", {confirmation.request_id: False})
    assert reply.text == "OK, I left it out."
    assert agent.state("s1").cart == []
    result = tool_responses(llm.requests[-1], "add_to_cart")[-1]
    assert result["status"] == "rejected"
    assert result["remaining_items"] == [] and result["note"] == "the cart is empty"
    assert result["changes"] == [
        {
            "product_id": "30173510",
            "title": "Acme Smart Radiator Thermostat",  # named from the catalog, although not in the cart
            "variant": None,
            "subtitle": None,
            "quantity_changed": 0,
            "remaining_of_product": 0,
            "note": "none of this product left in the cart",
        }
    ]


def test_remove_of_the_last_units_reports_none_left():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30387250"]),
            text_response("Added."),
            call_response("remove_from_cart", product_ids=["30387250"]),
            text_response("Removed."),
        ]
    )
    agent = service(llm)
    [add] = agent.chat("s1", "add the bridge").pending_confirmations
    agent.confirm("s1", {add.request_id: True})
    [remove] = agent.chat("s1", "remove the bridge").pending_confirmations
    assert (remove.action, remove.lines[0].quantity, remove.lines[0].in_cart) == ("remove", None, 1)
    agent.confirm("s1", {remove.request_id: True})
    result = tool_responses(llm.requests[-1], "remove_from_cart")[-1]
    change = result["changes"][0]
    assert (result["status"], change["quantity_changed"], change["remaining_of_product"]) == ("ok", 1, 0)
    assert result["remaining_items"] == []
    assert agent.state("s1").cart == []


def test_interface_edit_flags_the_cart_for_a_new_look():
    llm = ScriptedLlm(
        script=[call_response("add_to_cart", product_ids=["30173510"], quantities=[3]), text_response("ok")]
    )
    agent = service(llm)
    [confirmation] = agent.chat("s1", "add three thermostats").pending_confirmations
    agent.confirm("s1", {confirmation.request_id: True})
    assert "# Cart status" not in build_instruction(SimpleNamespace(state=_raw_state(agent)))

    agent.set_cart_quantity("s1", "30173510", 1)
    session = agent.state("s1")
    assert [(i.product_id, i.quantity) for i in session.cart] == [("30173510", 1)]
    assert session.cart_changed_by_user
    assert "changed the cart in the interface" in build_instruction(SimpleNamespace(state=_raw_state(agent)))

    llm.script = [call_response("view_cart"), text_response("You have one thermostat.")]
    reply = agent.chat("s1", "what is in my cart?")
    assert [c.name for c in reply.trace.tool_calls] == ["view_cart"]
    assert reply.trace.tool_calls[0].response is not None
    assert reply.trace.tool_calls[0].response["item_count"] == 1
    assert not agent.state("s1").cart_changed_by_user


def test_first_turn_asks_for_the_cart_check():
    llm = ScriptedLlm(script=[call_response("view_cart"), text_response("Hi! Your cart is empty.")])
    agent = service(llm)
    reply = agent.chat("s1", "hi")
    assert "call view_cart once" in str(llm.requests[0].config.system_instruction)
    assert reply.trace.tool_calls[0].response == {
        "status": "ok",
        "items": [],
        "item_count": 0,
        "cart_total": 0.0,
        "note": "the cart is empty",
    }
    assert agent.state("s1").cart_checked
    agent.chat("s1", "thanks")
    assert "# Cart status" not in str(llm.requests[-1].config.system_instruction)


def test_unknown_product_fails_at_once_so_the_model_retries_without_the_customer_seeing_it():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30173510", "90000001"], quantities=[8, 1]),
            call_response("add_to_cart", product_ids=["30173510", "30387250"], quantities=[8, 1]),
            text_response("Done, both are in your cart."),
        ]
    )
    agent = service(llm)
    pending = agent.chat("s1", "Add eight thermostats and the bridge they need")
    [confirmation] = pending.pending_confirmations  # only the retried call reaches the customer
    assert [(line.product_id, line.quantity) for line in confirmation.lines] == [("30173510", 8), ("30387250", 1)]
    assert agent.state("s1").cart == []
    [result] = tool_responses(llm.requests[-1], "add_to_cart")
    assert (result["status"], result["errors"][0]["product_id"]) == ("not_found", "90000001")
    assert [c["quantity_changed"] for c in result["changes"]] == [0, 0]
    assert "not shown this change" in result["message"] and "search_products" in result["message"]

    reply = agent.confirm("s1", {confirmation.request_id: True})
    assert reply.text == "Done, both are in your cart."
    assert [(i.product_id, i.quantity) for i in agent.state("s1").cart] == [("30173510", 8), ("30387250", 1)]


def test_remove_of_a_product_not_in_the_cart_fails_at_once():
    llm = ScriptedLlm(
        script=[call_response("remove_from_cart", product_ids=["30173510"]), text_response("It is not in your cart.")]
    )
    agent = service(llm)
    reply = agent.chat("s1", "Remove the thermostat")
    assert reply.pending_confirmations == []
    [result] = tool_responses(llm.requests[-1], "remove_from_cart")
    assert (result["status"], result["errors"][0]["message"]) == ("invalid_input", "not in the cart")
    assert "view_cart" in result["message"]


def test_invalid_arguments_fail_at_once():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30173510"], quantities=[1, 2]),
            text_response("Something went wrong."),
        ]
    )
    agent = service(llm)
    assert agent.chat("s1", "Add the thermostat").pending_confirmations == []
    [result] = tool_responses(llm.requests[-1], "add_to_cart")
    assert result["status"] == "invalid_input"
    assert result["message"].startswith("Nothing was changed: quantities must have one entry per product id")
    assert agent.state("s1").cart == []


def test_several_products_are_confirmed_together():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30173510", "30387250"], quantities=[2, 1]),
            text_response("Both are in your cart."),
        ]
    )
    agent = service(llm)
    [confirmation] = agent.chat("s1", "Add two thermostats and the bridge").pending_confirmations
    assert [(line.product_id, line.quantity) for line in confirmation.lines] == [("30173510", 2), ("30387250", 1)]
    assert confirmation.total == 158.98
    agent.confirm("s1", {confirmation.request_id: True})
    assert [(i.product_id, i.quantity) for i in agent.state("s1").cart] == [("30173510", 2), ("30387250", 1)]
    result = tool_responses(llm.requests[-1], "add_to_cart")[-1]
    assert [c["remaining_of_product"] for c in result["changes"]] == [2, 1]


def test_several_units_of_a_central_unit_are_refused_without_a_confirmation_card():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30387250", "30173510"], quantities=[6, 6]),
            text_response("One bridge runs all six thermostats. Do you really want six bridges?"),
        ]
    )
    agent = service(llm)
    reply = agent.chat("s1", "Add whatever is needed to control 6 thermostats")
    assert reply.pending_confirmations == []  # nothing for the customer to confirm
    assert reply.text.startswith("One bridge")
    assert agent.state("s1").cart == []
    result = tool_responses(llm.requests[-1], "add_to_cart")[-1]
    assert result["status"] == "needs_clarification"  # not replaced by the "awaiting_confirmation" callback
    assert result["central_units"] == [{"product_id": "30387250", "title": "Acme Bridge", "units_in_cart_after": 6}]
    assert [c["quantity_changed"] for c in result["changes"]] == [0, 0]


def test_a_second_unit_of_a_central_unit_already_in_the_cart_is_refused_too():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30387250"]),
            text_response("Added."),
            call_response("add_to_cart", product_ids=["30387250"]),
            text_response("You already have one bridge. Do you need a second one?"),
        ]
    )
    agent = service(llm)
    [confirmation] = agent.chat("s1", "Add the bridge").pending_confirmations
    agent.confirm("s1", {confirmation.request_id: True})
    reply = agent.chat("s1", "Add the bridge")
    assert reply.pending_confirmations == []
    assert [(i.product_id, i.quantity) for i in agent.state("s1").cart] == [("30387250", 1)]


def test_the_same_add_in_the_same_turn_is_refused_again():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30387250"], quantities=[2]),
            call_response("add_to_cart", product_ids=["30387250"], quantities=[2]),
            text_response("Do you really need two bridges?"),
        ]
    )
    agent = service(llm)
    reply = agent.chat("s1", "Add two bridges")
    assert reply.pending_confirmations == []  # the model has to ask the customer first
    statuses = [r["status"] for r in tool_responses(llm.requests[-1], "add_to_cart")]
    assert statuses == ["needs_clarification", "needs_clarification"]


def test_several_units_of_a_central_unit_the_customer_insisted_on_wait_for_confirmation():
    llm = ScriptedLlm(
        script=[
            call_response("add_to_cart", product_ids=["30387250"], quantities=[2]),
            text_response("One bridge usually runs a whole home. Do you really need two?"),
            call_response("add_to_cart", product_ids=["30387250"], quantities=[2]),
            text_response("Both bridges are in your cart."),
        ]
    )
    agent = service(llm)
    assert agent.chat("s1", "Add two bridges").pending_confirmations == []
    [confirmation] = agent.chat("s1", "Yes, I really need two bridges, one per house").pending_confirmations
    assert [(line.product_id, line.quantity) for line in confirmation.lines] == [("30387250", 2)]
    agent.confirm("s1", {confirmation.request_id: True})
    assert [(i.product_id, i.quantity) for i in agent.state("s1").cart] == [("30387250", 2)]


def _raw_state(agent: AgentService) -> dict[str, Any]:
    session = agent._loop.run(agent._sessions.get_or_create("s1", "customer"))
    return dict(session.state)
