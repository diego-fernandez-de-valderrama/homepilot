"""Command line helpers: `check` (infrastructure), `init-memory` (customer memory database), `smoke`
(recommendation pipeline) and `chat` (terminal chat).

uv run python -m smart_home_agent check
uv run python -m smart_home_agent init-memory
uv run python -m smart_home_agent smoke
uv run python -m smart_home_agent chat [--user ID]
uv run python -m smart_home_agent guardrail-eval [--sweep] [--record]
uv run python -m smart_home_agent upsell-eval
uv run python -m smart_home_agent variant-eval
uv run python -m smart_home_agent conversation-eval [--case NAME ...] [--repeat N]
"""

import argparse
import json
import sys
import uuid
from typing import TYPE_CHECKING

from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container
from smart_home_agent.models.cart import CartConfirmation
from smart_home_agent.models.recommendation import RecommendationRequest
from smart_home_agent.models.rich import to_plain

if TYPE_CHECKING:
    from smart_home_agent.agent.trace import AgentReply
    from smart_home_agent.config import Settings


def check() -> int:
    settings = get_settings()
    container = build_container(settings)
    print(f"PostgreSQL active products : {container.catalog.count_active()}")
    print(f"Qdrant points              : {container.index.count()} ({settings.qdrant.collection})")
    print(f"Indexed embedding model    : {container.index.indexed_embedding_model()}")
    print(f"Query embedding model      : {container.index.query_embedding_model}")
    print(f"Points with another model  : {container.index.points_with_other_model()}")
    print(f"Agent model                : {settings.agent.model}")
    print(f"Input guardrail            : {'on' if container.guardrail else 'off'}")
    print(f"Output check               : {'on' if settings.agent.guardrail_output_check else 'off'}")
    print(f"Customer memory            : {_memory_status(settings)}")
    return 0


def _memory_status(settings: "Settings") -> str:
    from sqlalchemy.exc import OperationalError

    from smart_home_agent.memory.database import create_memory_engine, current_revision

    if not settings.agent.memory_enabled:
        return "off"
    engine = create_memory_engine(settings.postgres, settings.agent.memory_db)
    try:
        revision = current_revision(engine)
    except OperationalError:
        return f"database {settings.agent.memory_db!r} not reachable (run init-memory)"
    finally:
        engine.dispose()
    return f"{settings.agent.memory_db} (revision {revision})" if revision else "not initialized (run init-memory)"


def init_memory() -> int:
    """Creates the customer memory database on the POSTGRES_* server and migrates it (idempotent)."""
    from smart_home_agent.memory.database import create_memory_engine, ensure_database, upgrade_to_head

    settings = get_settings()
    name = settings.agent.memory_db
    created = ensure_database(settings.postgres, name)
    engine = create_memory_engine(settings.postgres, name)
    try:
        upgrade_to_head(engine)
    finally:
        engine.dispose()
    print(f"Customer memory database {name!r} {'created and ' if created else ''}migrated to head.")
    return 0


def smoke() -> int:
    """Services only (one embedding call, no chat model): thermostat for Google Home up to 150 EUR."""
    container = build_container(get_settings())
    request = RecommendationRequest(
        need="Thermostat für Google Home", category="heating_control", max_price=150, must_support=["google_home"]
    )
    result = container.services.recommendation.recommend(request)
    summary = {
        "best_match": result.best_match,
        "confirmed": [(r.product.id, r.product.title, r.product.price) for r in result.confirmed],
        "unconfirmed": [(r.product.id, r.product.title, r.compatibility.value) for r in result.unconfirmed],
        "excluded": result.excluded,
        "upsell": result.upsell.model_dump() if result.upsell else None,
        "accessories": [a.model_dump() for a in result.accessories],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def chat(user_id: str) -> int:
    from smart_home_agent.agent.orchestrator import AgentService, build_agent

    settings = get_settings()
    container = build_container(settings)
    agent = build_agent(container.services, settings, container.guardrail)
    services = container.services
    service = AgentService(agent, settings.agent.app_name, services.rich_content, services.cart, services.profile)
    session_id = str(uuid.uuid4())
    print(f"HomePilot, customer {user_id!r} (Ctrl-D to quit)")
    for line in sys.stdin:
        if not line.strip():
            continue
        reply = service.chat(session_id, line.strip(), user_id)
        _print_reply(reply)
        # Cart changes wait for an explicit yes, like the confirmation card in the web UI.
        while reply.pending_confirmations:
            decisions = {c.request_id: _ask(c) for c in reply.pending_confirmations}
            reply = service.confirm(session_id, decisions, user_id)
            _print_reply(reply)
    return 0


def _print_reply(reply: "AgentReply") -> None:
    tools = ", ".join(c.name for c in reply.trace.tool_calls) or "none"
    guardrail = reply.guardrail
    verdict = guardrail.input.category if guardrail and guardrail.input else "n/a"
    replaced = f", reply: {guardrail.response_type}" if guardrail and guardrail.response_type else ""
    text = to_plain(reply.text, reply.rich.titles(), reply.rich.names()) if reply.rich else to_plain(reply.text, {})
    print(f"\n{text}\n  [tools: {tools}] [guardrail: {verdict}{replaced}]\n")


def _ask(change: CartConfirmation) -> bool:
    verb = "Add to" if change.action == "add" else "Remove from"
    print(f"{verb} the cart:")
    for line in change.lines:
        title = line.product.name if line.product else f"product {line.product_id} (not in the catalog)"
        amount = "all units of" if line.quantity is None else f"{line.quantity} x"
        print(f"  - {amount} {title}")
    answer = input("Confirm? [y/N] ")
    return answer.strip().lower() in {"y", "yes", "j", "ja"}


def guardrail_eval(sweep: bool, record: bool) -> int:
    """Embeds prototypes and evaluation cases (a few batched embedding calls, no chat model)."""
    from smart_home_agent.guardrail.eval import run

    return run(get_settings(), do_sweep=sweep, record=record)


def upsell_eval() -> int:
    """Upselling KPI over a fixed request set (one embedding per case, no chat model)."""
    from smart_home_agent.upsell_eval import evaluate, report

    container = build_container(get_settings())
    results = evaluate(container.services.recommendation.recommend)
    print(report(results))
    return 1 if any(r.guard_failures for r in results) else 0


def variant_eval() -> int:
    """Product version grouping over a fixed request set (one embedding per case, no chat model)."""
    from smart_home_agent.variant_eval import evaluate, report

    container = build_container(get_settings())
    results = evaluate(container.services.recommendation.recommend)
    print(report(results))
    return 1 if any(r.guard_failures for r in results) else 0


def conversation_eval(names: list[str] | None, repeat: int) -> int:
    """Fixed conversations through the real agent (live chat model); deterministic checks per turn."""
    from smart_home_agent.agent.orchestrator import AgentService, build_agent
    from smart_home_agent.container import build_profile_store
    from smart_home_agent.conversation_eval import EVAL_USER, evaluate, regressions, report, select

    conversations = select(names)
    settings = get_settings()
    container = build_container(settings)
    services = container.services
    agent = build_agent(services, settings, container.guardrail)
    service = AgentService(agent, settings.agent.app_name, services.rich_content, services.cart, services.profile)
    results = []
    used: list[str] = []
    try:
        results = evaluate(service, conversations, repeat, used_user_ids=used)
    finally:
        # Every run used its own customer id; remove what the memory conversations stored, also after a crash,
        # and customers left over by earlier crashed evaluations (the generated id format only).
        if (store := build_profile_store(settings)) is not None:
            leftovers = [c.user_id for c in store.customers() if EVAL_USER.match(c.user_id)]
            store.delete_customers(list(dict.fromkeys([*used, *leftovers])))
    print(report(results, conversations))
    return 1 if regressions(results) else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="smart_home_agent")
    commands = {
        "check": check,
        "init-memory": init_memory,
        "smoke": smoke,
        "upsell-eval": upsell_eval,
        "variant-eval": variant_eval,
    }
    parser.add_argument("command", choices=[*commands, "chat", "guardrail-eval", "conversation-eval"])
    parser.add_argument("--sweep", action="store_true", help="guardrail-eval: print score separation per category")
    parser.add_argument("--record", action="store_true", help="guardrail-eval: rewrite the offline test fixture")
    parser.add_argument("--user", default="customer", help="chat: customer id (each customer has their own memory)")
    parser.add_argument("--case", action="append", help="conversation-eval: run only this conversation (repeatable)")
    parser.add_argument("--repeat", type=int, default=1, help="conversation-eval: runs per conversation")
    args = parser.parse_args()
    if args.command == "conversation-eval":
        return conversation_eval(args.case, max(1, args.repeat))
    if args.command == "guardrail-eval":
        return guardrail_eval(args.sweep, args.record)
    if args.command == "chat":
        return chat(args.user)
    return commands[args.command]()


if __name__ == "__main__":
    sys.exit(main())
