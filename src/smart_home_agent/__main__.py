"""Command line helpers: `check` (infrastructure), `smoke` (recommendation pipeline) and `chat` (terminal chat).

uv run python -m smart_home_agent check
uv run python -m smart_home_agent smoke
uv run python -m smart_home_agent chat
"""

import argparse
import json
import sys
import uuid

from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container
from smart_home_agent.models.recommendation import RecommendationRequest


def check() -> int:
    settings = get_settings()
    container = build_container(settings)
    print(f"PostgreSQL active products : {container.catalog.count_active()}")
    print(f"Qdrant points              : {container.index.count()} ({settings.qdrant.collection})")
    print(f"Indexed embedding model    : {container.index.indexed_embedding_model()}")
    print(f"Query embedding model      : {container.index.query_embedding_model}")
    print(f"Agent model                : {settings.agent.model}")
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
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def chat() -> int:
    from smart_home_agent.agent.orchestrator import AgentService, build_agent

    settings = get_settings()
    container = build_container(settings)
    service = AgentService(build_agent(container.services, settings), settings.agent.app_name)
    session_id = str(uuid.uuid4())
    print("HomePilot (Ctrl-D to quit)")
    for line in sys.stdin:
        if not line.strip():
            continue
        reply = service.chat(session_id, line.strip())
        tools = ", ".join(c.name for c in reply.trace.tool_calls) or "none"
        print(f"\n{reply.text}\n  [tools: {tools}]\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="smart_home_agent")
    parser.add_argument("command", choices=["check", "smoke", "chat"])
    command = parser.parse_args().command
    return {"check": check, "smoke": smoke, "chat": chat}[command]()


if __name__ == "__main__":
    sys.exit(main())
