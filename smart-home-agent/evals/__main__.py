"""Evaluation commands: `guardrail` (input classifier and output check), `upsell` (upselling KPI), `variant`
(product version grouping) and `conversation` (regression conversations through the live agent).

uv run python -m evals guardrail [--sweep] [--record]
uv run python -m evals upsell
uv run python -m evals variant
uv run python -m evals conversation [--case NAME ...] [--repeat N]
"""

from typing import Annotated

import typer

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
    from smart_home_agent.agent import AgentService, build_agent
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


app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("guardrail")
def _guardrail_command(
    sweep: Annotated[bool, typer.Option(help="Print score separation per category.")] = False,
    record: Annotated[bool, typer.Option(help="Rewrite the offline test fixture.")] = False,
) -> None:
    """Guardrail metrics (input classifier and output check)."""
    raise typer.Exit(guardrail(sweep, record))


@app.command("upsell")
def _upsell_command() -> None:
    """Upselling KPI over fixed requests."""
    raise typer.Exit(upsell())


@app.command("variant")
def _variant_command() -> None:
    """Product version grouping over fixed requests."""
    raise typer.Exit(variant())


@app.command("conversation")
def _conversation_command(
    case: Annotated[list[str] | None, typer.Option(help="Run only this conversation (repeatable).")] = None,
    repeat: Annotated[int, typer.Option(min=1, help="Runs per conversation.")] = 1,
) -> None:
    """Regression conversations through the live agent."""
    raise typer.Exit(conversation(case, repeat))


if __name__ == "__main__":
    app(prog_name="evals")
