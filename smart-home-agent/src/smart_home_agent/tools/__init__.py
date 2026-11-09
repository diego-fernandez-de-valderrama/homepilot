"""ADK function tools. Import everything from here:

    from smart_home_agent.tools import ToolRegistry, CartResultCallback, ...

Flow: `ToolRegistry(services).build()` creates one instance of each tool class and wraps its tool method in a
`ThreadedFunctionTool` (sync tools run in worker threads, off the shared agent event loop); the cart changes in
`CONFIRMED_TOOLS` wait for the customer's confirmation. `CartResultCallback` is the agent's `after_tool_callback`.

Each tool is a thin adapter, one class per tool, whose one public method is the ADK tool (its name, docstring
and parameters are what the model sees): resolve free text to canonical ids (`Vocabulary`), validate the
arguments (Pydantic), call a service, update the `SessionState` and return a dict with `status`. Expected
failures become status results (`needs_clarification`, `not_found`, `invalid_input`, ...) via `tool_errors`.
No database or Qdrant access happens here.

One subpackage per tool domain, in the order of a typical conversation (internals in `_modules`):

- `preferences/`: `remember_preferences` (this conversation only).
- `profile/`: `remember_customer_facts` (lasting customer memory; only when a profile store is configured).
- `catalog/`: `search_products`, `filter_products`, `get_product`.
- `recommendation/`: `recommend_products`, the main recommendation pipeline.
- `compatibility/`: `check_compatibility`.
- `comparison/`: `compare_products`.
- `evidence/`: `get_evidence`.
- `cart/`: `view_cart`, `add_to_cart`, `remove_from_cart`, their confirmation rule and result callback.
- `_base/`: the `HomePilotTool` base class, `tool_errors`, `InvalidToolInput`.
"""

from smart_home_agent.tools.cart import CONFIRMED_TOOLS, CartResultCallback
from smart_home_agent.tools.threaded_function_tool import ThreadedFunctionTool
from smart_home_agent.tools.tool_registry import ToolRegistry

__all__ = ["CONFIRMED_TOOLS", "CartResultCallback", "ThreadedFunctionTool", "ToolRegistry"]
