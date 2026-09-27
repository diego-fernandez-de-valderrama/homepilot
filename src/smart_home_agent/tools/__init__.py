"""ADK function tools. Each tool is a thin adapter: resolve and validate input, call a service,
return a JSON-serializable dict. No database or Qdrant access happens here."""

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from google.adk.tools import FunctionTool

from smart_home_agent.container import Services
from smart_home_agent.tools.cart import (
    CONFIRMED_TOOLS,
    make_add_confirmation_rule,
    make_add_to_cart,
    make_remove_from_cart,
    make_view_cart,
)
from smart_home_agent.tools.catalog import make_filter_products, make_get_product, make_search_products
from smart_home_agent.tools.comparison import make_compare_products
from smart_home_agent.tools.compatibility import make_check_compatibility
from smart_home_agent.tools.evidence import make_get_evidence
from smart_home_agent.tools.preferences import make_remember_preferences
from smart_home_agent.tools.profile import make_remember_customer_facts
from smart_home_agent.tools.recommend import make_recommend_products

__all__ = ["CONFIRMED_TOOLS", "build_tools"]


def build_tools(services: Services) -> list[FunctionTool]:
    functions = [
        make_recommend_products(services),
        make_search_products(services),
        make_filter_products(services),
        make_get_product(services),
        make_check_compatibility(services),
        make_compare_products(services),
        make_get_evidence(services),
        make_remember_preferences(),
        make_view_cart(services),
        make_add_to_cart(services),
        make_remove_from_cart(services),
    ]
    if services.profile is not None:
        functions.append(make_remember_customer_facts(services.profile))
    # The customer confirms every cart change in the interface before ADK runs the tool (an add refused at once,
    # see make_add_confirmation_rule, has nothing to confirm).
    rules: dict[str, bool | Callable[..., bool]] = {"add_to_cart": make_add_confirmation_rule(services)}
    return [
        ThreadedFunctionTool(f, require_confirmation=rules.get(f.__name__, f.__name__ in CONFIRMED_TOOLS))
        for f in functions
    ]


class ThreadedFunctionTool(FunctionTool):
    """Runs a synchronous tool function in a worker thread.

    All sessions share one agent event loop (AgentService). ADK calls sync tools directly on that loop in
    `run_async` (its `tool_thread_pool_config` only applies to live mode), so one customer's database, Qdrant
    and embedding calls would block every other conversation. `asyncio.to_thread` copies the context, and
    each call has its own ToolContext, so state writes stay per call. `func` stays the plain function.
    """

    async def _invoke_callable(self, target: Callable[..., Any], args_to_call: dict[str, Any]) -> Any:
        if inspect.iscoroutinefunction(target):  # the tools here are plain functions
            return await super()._invoke_callable(target, args_to_call)
        return await asyncio.to_thread(target, **args_to_call)
