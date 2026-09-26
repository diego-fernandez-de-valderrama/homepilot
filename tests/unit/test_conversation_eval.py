from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from smart_home_agent import conversation_eval as ev
from smart_home_agent.agent.state import SessionState
from smart_home_agent.agent.trace import AgentReply, TurnTrace
from smart_home_agent.guardrail.callbacks import GuardrailReport
from smart_home_agent.guardrail.categories import Category, GuardrailDecision
from smart_home_agent.guardrail.output_check import Violation
from smart_home_agent.models.cart import CartChangeLine, CartConfirmation, CartItem
from smart_home_agent.models.profile import CustomerFact, CustomerProfile, FactKind
from smart_home_agent.models.rich import RichContent
from tests.fakes import product


def _reply(
    text: str = "Here you go.",
    calls: Sequence[tuple[str, dict[str, Any], dict[str, Any]]] = (),
    **fields: Any,
) -> AgentReply:
    trace = TurnTrace()
    for i, (name, args, response) in enumerate(calls):
        trace.add_call(str(i), name, args)
        trace.add_response(str(i), name, response)
    return AgentReply(
        text=text, detected_language=None, trace=trace, state=fields.pop("state", SessionState()), **fields
    )


def _check(check: ev.Check, reply: AgentReply, previous: AgentReply | None = None) -> str | None:
    return check.test(ev.TurnContext(reply=reply, previous=previous))


def _decision(category: Category, blocked: bool) -> GuardrailDecision:
    return GuardrailDecision(
        category=category, top_category=category, score=0.9, margin=0.1, scores={}, blocked=blocked
    )


RECOMMEND = (
    "recommend_products",
    {"need": "thermostat", "must_support": ["Google Home"]},
    {"status": "ok", "request": {"must_support": ["google_home"], "max_price": 150.0, "category": "heating_control"}},
)
FILTER = (
    "filter_products",
    {"supports": ["Siri"]},
    {"status": "ok", "criteria": {"supports": ["apple_siri"], "max_price": 20.0, "category": "smart_plug"}},
)
COMPATIBILITY = (
    "check_compatibility",
    {"product_ids": ["11111111"], "requirements": ["Matter"]},
    {"status": "ok", "results": [{"checks": [{"term": "matter", "status": "unknown"}]}]},
)


def test_searched_reads_the_resolved_criteria_of_recommend_and_filter():
    assert (
        _check(
            ev.searched(supports=["google_home"], max_price=150, category="heating_control"), _reply(calls=[RECOMMEND])
        )
        is None
    )
    assert _check(ev.searched(supports=["apple_siri"], max_price=20), _reply(calls=[FILTER])) is None
    failure = _check(ev.searched(max_price=80), _reply(calls=[RECOMMEND]))
    assert failure and "max_price 150.0, expected 80" in failure
    assert _check(ev.searched(), _reply()) == "no successful recommend_products / filter_products call"


def test_terms_come_from_every_resolving_tool_and_wrong_concepts_fail():
    reply = _reply(calls=[RECOMMEND, FILTER, COMPATIBILITY])
    assert ev.resolved_terms(reply) == {"google_home", "apple_siri", "matter"}
    assert _check(ev.uses_terms("apple_siri", "matter"), reply) is None
    assert _check(ev.never_terms("apple_home"), reply) is None
    assert _check(ev.never_terms("apple_siri"), reply) == "wrong concept used: apple_siri"
    failed = ("recommend_products", {}, {"status": "needs_clarification", "request": {"must_support": ["apple_home"]}})
    assert ev.resolved_terms(_reply(calls=[failed])) == set()  # only what a tool actually ran counts


def test_blocked_requires_the_category_and_no_tool_call():
    blocked = GuardrailReport(input=_decision(Category.ELECTRICAL, True), response_type="ELECTRICAL")
    assert _check(ev.blocked(Category.ELECTRICAL), _reply(guardrail=blocked)) is None
    assert _check(ev.blocked(Category.PROMPT_INJECTION), _reply(guardrail=blocked))
    assert _check(ev.blocked(Category.ELECTRICAL), _reply(calls=[RECOMMEND], guardrail=blocked))
    allowed = GuardrailReport(input=_decision(Category.SMART_HOME, False))
    assert _check(ev.not_blocked(), _reply(guardrail=allowed)) is None
    assert _check(ev.not_blocked(), _reply(guardrail=blocked)) == "blocked as ELECTRICAL"


def test_language_fails_only_on_the_other_language():
    check = ev.reply_language("de")
    assert _check(check, _reply("Das ist eine gute Wahl für dich, weil sie mit deinem System funktioniert.")) is None
    assert _check(check, _reply("OK.")) is None  # too short to tell
    assert _check(check, _reply("This is a good choice for you because it works with your system.")) is not None


def test_follow_up_must_use_the_previous_results():
    previous = _reply(state=SessionState(candidate_products=["11111111", "22222222"]))
    compare = ("compare_products", {"product_ids": ["11111111", "22222222"]}, {"status": "ok"})
    assert _check(ev.refers_to_previous_products("compare_products"), _reply(calls=[compare]), previous) is None
    assert _check(ev.compares(2), _reply(calls=[compare])) is None
    other = ("compare_products", {"product_ids": ["11111111", "99999999"]}, {"status": "ok"})
    assert _check(ev.refers_to_previous_products("compare_products"), _reply(calls=[other]), previous)


def test_cart_holds_exactly_what_was_confirmed():
    pending = [
        CartConfirmation(
            request_id="r1", action="add", lines=[CartChangeLine(product_id="11111111", quantity=1, product=None)]
        )
    ]
    previous = _reply(pending_confirmations=pending)
    applied = _reply(state=SessionState(cart=[CartItem(product_id="11111111", quantity=1)]))
    assert _check(ev.cart_applied(confirmed=True), applied, previous) is None
    assert _check(ev.cart_applied(confirmed=False), applied, previous) == "cart 11111111, expected none"
    assert _check(ev.cart_applied(confirmed=False), _reply(), previous) is None
    assert _check(ev.cart_change_pending("add", products=2), previous, _reply())


def test_a_confirmation_turn_without_a_pending_change_fails_without_calling_the_agent():
    service = ScriptedService([_reply("Do you also want the hub?")])
    conversation = ev.Conversation("c", "p", (ev.Turn(text="add it"), ev.Turn(confirm=True)))
    result = ev.run_conversation(service, conversation, "eval-1")
    assert result.turns[1].failures == ["confirm: no pending cart change"]
    assert [kind for kind, _, _ in service.calls] == ["chat"]


def test_cart_change_must_wait_for_confirmation():
    pending = [CartConfirmation(request_id="r1", action="add")]
    assert _check(ev.cart_change_pending("add"), _reply(pending_confirmations=pending), _reply()) is None
    applied = SessionState(cart=[CartItem(product_id="11111111", quantity=1)])
    assert _check(ev.cart_change_pending("add"), _reply(pending_confirmations=pending, state=applied), _reply())
    assert _check(ev.cart_size(1), _reply(state=applied)) is None


def _profile(*facts: tuple[FactKind, str, bool]) -> CustomerProfile:
    now = datetime.now(UTC)
    return CustomerProfile(
        user_id="u",
        facts=[
            CustomerFact(id=i, user_id="u", kind=k, value=v, label=v, evidence=v, created_at=now, active=active)
            for i, (k, v, active) in enumerate(facts)
        ],
    )


def test_memory_checks_read_active_facts_only():
    reply = _reply(profile=_profile((FactKind.NAME, "Anna", True), (FactKind.ECOSYSTEM, "apple_home", False)))
    assert _check(ev.remembers(FactKind.NAME, "anna"), reply) is None
    assert _check(ev.does_not_remember(FactKind.ECOSYSTEM, "apple_home"), reply) is None  # retracted
    assert _check(ev.remembers(FactKind.ECOSYSTEM, "google_home"), reply)


class ScriptedService:
    """Returns prepared replies in order and records how it was called."""

    def __init__(self, replies: list[AgentReply]) -> None:
        self.replies = replies
        self.calls: list[tuple[str, str, Any]] = []

    def chat(self, session_id: str, text: str, user_id: str) -> AgentReply:
        self.calls.append(("chat", session_id, text))
        return self.replies.pop(0)

    def confirm(self, session_id: str, decisions: dict[str, bool], user_id: str) -> AgentReply:
        self.calls.append(("confirm", session_id, decisions))
        return self.replies.pop(0)


def test_run_answers_pending_changes_and_opens_new_sessions():
    pending = [CartConfirmation(request_id="r1", action="add")]
    service = ScriptedService([_reply(pending_confirmations=pending), _reply(), _reply()])
    conversation = ev.Conversation(
        "c",
        "purpose",
        (ev.Turn(text="add it"), ev.Turn(confirm=True), ev.Turn(text="hi", new_session=True)),
    )
    result = ev.run_conversation(service, conversation, "eval-1")
    assert result.passed
    (_, first, _), (kind, second, decisions), (_, third, _) = service.calls
    assert (kind, decisions) == ("confirm", {"r1": True})
    assert first == second != third


def test_every_turn_needs_an_answer_the_output_check_kept():
    replaced = GuardrailReport(output_violations=[Violation(kind="unknown_product", detail="12345678")])
    service = ScriptedService([_reply(""), _reply(guardrail=replaced), _reply(guardrail=replaced)])
    turns = (ev.Turn(text="a"), ev.Turn(text="b"), ev.Turn(text="c", allow_fallback=True))
    result = ev.run_conversation(service, ev.Conversation("c", "p", turns), "eval-1")
    assert [bool(t.failures) for t in result.turns] == [True, True, False]
    assert result.turns[0].failures[0].startswith("answered")


def test_report_separates_regressions_from_known_issues():
    ok = ev.ConversationResult(name="ok", user_id="u1", turns=[ev.TurnResult(message="m", tools=[], failures=[])])
    bad = ev.TurnResult(message="m", tools=['recommend_products({"need": "x"})'], failures=["searched: no call"])
    flaky = [ok.model_copy(update={"name": "flaky"}), ev.ConversationResult(name="flaky", user_id="u2", turns=[bad])]
    known = ev.ConversationResult(name="known", user_id="u3", turns=[bad], known_issue="model guesses")
    results = [ok, *flaky, known]
    text = ev.report(
        results, [ev.Conversation("ok", "p"), ev.Conversation("flaky", "p"), ev.Conversation("known", "p")]
    )
    assert "PASS  ok (1/1)" in text
    assert "FLAKY flaky (1/2)" in text
    assert "KNOWN known (0/1)" in text
    assert 'tool recommend_products({"need": "x"})' in text
    assert ev.regressions(results) == [flaky[1]]


def test_every_conversation_has_checks_and_unique_names():
    names = [c.name for c in ev.CONVERSATIONS]
    assert len(names) == len(set(names))
    assert all(turn.checks or turn.new_session for c in ev.CONVERSATIONS for turn in c.turns)
    assert ev.select(["off_topic"])[0].name == "off_topic"


def test_shown_products_come_from_the_resolved_tags():
    shown = _reply(rich=RichContent(products={"11111111": product("11111111")}))
    assert _check(ev.shows_products(), shown) is None
    assert _check(ev.shows_products(), _reply()) == "no catalog product shown"
    assert _check(ev.shows_no_products(), shown) == "products shown: 11111111"
