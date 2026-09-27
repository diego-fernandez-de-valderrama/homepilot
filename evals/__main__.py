"""Evaluation commands: `guardrail` (input classifier and output check), `upsell` (upselling KPI), `variant`
(product version grouping) and `conversation` (regression conversations through the live agent).

uv run python -m evals guardrail [--sweep] [--record]
uv run python -m evals upsell
uv run python -m evals variant
uv run python -m evals conversation [--case NAME ...] [--repeat N]
"""

import argparse
import sys

from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container


def guardrail(sweep: bool, record: bool) -> int:
    """Embeds prototypes and evaluation cases (a few batched embedding calls, no chat model)."""
    from evals.guardrail import run

    return run(get_settings(), do_sweep=sweep, record=record)


def upsell() -> int:
    """Upselling KPI over a fixed request set (one embedding per case, no chat model)."""
    from evals.upsell import evaluate, report

    container = build_container(get_settings())
    results = evaluate(container.services.recommendation.recommend)
    print(report(results))
    return 1 if any(r.guard_failures for r in results) else 0


def variant() -> int:
    """Product version grouping over a fixed request set (one embedding per case, no chat model)."""
    from evals.variant import evaluate, report

    container = build_container(get_settings())
    results = evaluate(container.services.recommendation.recommend)
    print(report(results))
    return 1 if any(r.guard_failures for r in results) else 0


def conversation(names: list[str] | None, repeat: int) -> int:
    """Fixed conversations through the real agent (live chat model); deterministic checks per turn."""
    from evals.conversation import EVAL_USER, evaluate, regressions, report, select
    from smart_home_agent.agent.orchestrator import AgentService, build_agent
    from smart_home_agent.container import build_profile_store

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
    parser = argparse.ArgumentParser(prog="evals")
    parser.add_argument("command", choices=["guardrail", "upsell", "variant", "conversation"])
    parser.add_argument("--sweep", action="store_true", help="guardrail: print score separation per category")
    parser.add_argument("--record", action="store_true", help="guardrail: rewrite the offline test fixture")
    parser.add_argument("--case", action="append", help="conversation: run only this conversation (repeatable)")
    parser.add_argument("--repeat", type=int, default=1, help="conversation: runs per conversation")
    args = parser.parse_args()
    if args.command == "conversation":
        return conversation(args.case, max(1, args.repeat))
    if args.command == "guardrail":
        return guardrail(args.sweep, args.record)
    return {"upsell": upsell, "variant": variant}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
