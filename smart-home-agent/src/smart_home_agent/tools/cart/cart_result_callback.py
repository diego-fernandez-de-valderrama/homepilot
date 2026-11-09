import asyncio
from typing import Any

from google.adk.tools import BaseTool, ToolContext

from smart_home_agent.container import Services
from smart_home_agent.session import StateStore
from smart_home_agent.tools.cart._cart_tool import CartTool
from smart_home_agent.tools.cart._change_report import ChangeReport
from smart_home_agent.tools.cart.confirmed_tools import CONFIRMED_TOOLS

_AWAITING = "The customer is asked to confirm this change in the interface. It is not applied yet."
_REJECTED = "The customer cancelled this change in the interface. The cart was not changed."


class CartResultCallback:
    """`after_tool_callback`: ADK answers an unconfirmed or cancelled add/remove itself, without running the
    tool. Its generic error is replaced by the same result shape the tool returns, with the unchanged cart."""

    def __init__(self, services: Services) -> None:
        self._services = services

    async def __call__(
        self, tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: dict[str, Any]
    ) -> dict[str, Any] | None:
        action = CONFIRMED_TOOLS.get(tool.name)
        confirmation = tool_context.tool_confirmation
        if action is None or (confirmation is not None and confirmation.confirmed):
            return None  # not a cart change, or the tool really ran and built its own result
        if confirmation is None and "status" in tool_response:
            # CartConfirmationRule let the tool refuse the change at once (the tool's results always carry a
            # status; ADK's own answer to a call waiting for confirmation only an error)
            return None
        session = CartTool.synced_state(tool_context)
        StateStore.save(tool_context, session)
        status, message = ("awaiting_confirmation", _AWAITING) if confirmation is None else ("rejected", _REJECTED)
        ids = CartTool.product_ids(args.get("product_ids"))

        def build() -> dict[str, Any]:  # database reads: off the shared agent event loop
            view = self._services.cart.view(session.cart)
            return ChangeReport.build(status, action, ids, view, view, message, catalog=self._services.catalog)

        return await asyncio.to_thread(build)
