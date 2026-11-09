"""Command line helpers: `check` (infrastructure), `init-memory` (customer memory database), `smoke`
(recommendation pipeline) and `chat` (terminal chat).

uv run python -m smart_home_agent check
uv run python -m smart_home_agent init-memory
uv run python -m smart_home_agent smoke
uv run python -m smart_home_agent chat [--user ID]

Evaluations live in the separate `evals` package: `uv run python -m evals --help`.
"""

import json
import sys
import uuid
from typing import TYPE_CHECKING, Annotated

import typer

from smart_home_agent.answer_tags import PlainTextRenderer
from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container
from smart_home_agent.models import CartConfirmation, RecommendationRequest

if TYPE_CHECKING:
    from smart_home_agent.agent import AgentReply
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

    from smart_home_agent.repositories import MemoryDatabase

    if not settings.agent.memory_enabled:
        return "off"
    engine = MemoryDatabase(settings.postgres, settings.agent.memory_db).create_engine()
    try:
        revision = MemoryDatabase.current_revision(engine)
    except OperationalError:
        return f"database {settings.agent.memory_db!r} not reachable (run init-memory)"
    finally:
        engine.dispose()
    return f"{settings.agent.memory_db} (revision {revision})" if revision else "not initialized (run init-memory)"


def init_memory() -> int:
    """Creates the customer memory database on the POSTGRES_* server and migrates it (idempotent)."""
    from smart_home_agent.repositories import MemoryDatabase

    settings = get_settings()
    name = settings.agent.memory_db
    database = MemoryDatabase(settings.postgres, name)
    created = database.ensure_exists()
    engine = database.create_engine()
    try:
        MemoryDatabase.upgrade_to_head(engine)
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
    from smart_home_agent.agent import AgentService, build_agent

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
    renderer = PlainTextRenderer(reply.rich.titles(), reply.rich.names()) if reply.rich else PlainTextRenderer({})
    text = renderer.render(reply.text)
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


app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("check")
def _check_command() -> None:
    """PostgreSQL/Qdrant counts, embedding model consistency and customer memory revision."""
    raise typer.Exit(check())


@app.command("init-memory")
def _init_memory_command() -> None:
    """Create and migrate the customer memory database (idempotent)."""
    raise typer.Exit(init_memory())


@app.command("smoke")
def _smoke_command() -> None:
    """Recommendation pipeline only (one embedding call, no chat model)."""
    raise typer.Exit(smoke())


@app.command("chat")
def _chat_command(
    user: Annotated[str, typer.Option(help="Customer id (each customer has their own memory).")] = "customer",
) -> None:
    """Terminal chat with the agent."""
    raise typer.Exit(chat(user))


if __name__ == "__main__":
    app(prog_name="smart_home_agent")
