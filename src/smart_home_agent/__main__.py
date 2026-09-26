"""Command line helpers: `check` (infrastructure), `smoke` (recommendation pipeline) and `chat` (terminal chat).

uv run python -m smart_home_agent check
uv run python -m smart_home_agent smoke
uv run python -m smart_home_agent chat
uv run python -m smart_home_agent guardrail-eval [--sweep] [--record]
uv run python -m smart_home_agent upsell-eval
"""

import argparse
import json
import sys
import uuid

from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container
from smart_home_agent.models.recommendation import RecommendationRequest
from smart_home_agent.models.rich import to_plain


def check() -> int:
    settings = get_settings()
    container = build_container(settings)
    print(f"PostgreSQL active products : {container.catalog.count_active()}")
    print(f"Qdrant points              : {container.index.count()} ({settings.qdrant.collection})")
    print(f"Indexed embedding model    : {container.index.indexed_embedding_model()}")
    print(f"Query embedding model      : {container.index.query_embedding_model}")
    print(f"Agent model                : {settings.agent.model}")
    print(f"Input guardrail            : {'on' if container.guardrail else 'off'}")
    print(f"Output check               : {'on' if settings.agent.guardrail_output_check else 'off'}")
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


def chat() -> int:
    from smart_home_agent.agent.orchestrator import AgentService, build_agent

    settings = get_settings()
    container = build_container(settings)
    agent = build_agent(container.services, settings, container.guardrail)
    service = AgentService(agent, settings.agent.app_name, container.services.rich_content)
    session_id = str(uuid.uuid4())
    print("HomePilot (Ctrl-D to quit)")
    for line in sys.stdin:
        if not line.strip():
            continue
        reply = service.chat(session_id, line.strip())
        tools = ", ".join(c.name for c in reply.trace.tool_calls) or "none"
        guardrail = reply.guardrail
        verdict = guardrail.input.category if guardrail and guardrail.input else "n/a"
        replaced = f", reply: {guardrail.response_type}" if guardrail and guardrail.response_type else ""
        text = to_plain(reply.text, reply.rich.titles() if reply.rich else {})
        print(f"\n{text}\n  [tools: {tools}] [guardrail: {verdict}{replaced}]\n")
    return 0


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="smart_home_agent")
    parser.add_argument("command", choices=["check", "smoke", "chat", "guardrail-eval", "upsell-eval"])
    parser.add_argument("--sweep", action="store_true", help="guardrail-eval: print score separation per category")
    parser.add_argument("--record", action="store_true", help="guardrail-eval: rewrite the offline test fixture")
    args = parser.parse_args()
    if args.command == "guardrail-eval":
        return guardrail_eval(args.sweep, args.record)
    return {"check": check, "smoke": smoke, "chat": chat, "upsell-eval": upsell_eval}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
