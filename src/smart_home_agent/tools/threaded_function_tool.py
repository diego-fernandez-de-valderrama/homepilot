import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from google.adk.tools import FunctionTool


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
