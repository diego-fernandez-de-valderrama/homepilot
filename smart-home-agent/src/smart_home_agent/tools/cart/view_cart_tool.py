from google.adk.tools import ToolContext

from smart_home_agent.session import StateStore
from smart_home_agent.tools._base import ToolResult, tool_errors
from smart_home_agent.tools.cart._cart_tool import CartTool


class ViewCartTool(CartTool):
    @tool_errors
    def view_cart(self, tool_context: ToolContext) -> ToolResult:
        """List the products in the customer's shopping cart of this conversation, with quantities and
        catalog prices. Call it at the start of a conversation and whenever you are told the customer changed
        the cart in the interface.
        """
        session = self.synced_state(tool_context)
        view = self._services.cart.view(session.cart)
        StateStore.save(tool_context, session)
        result = self.ok(items=view.for_model(), item_count=view.item_count, cart_total=view.total)
        if not view.lines:
            result["note"] = "the cart is empty"
        if view.has_unpriced:
            result["unpriced_note"] = "some products have no listed price and are not in the total"
        return result
