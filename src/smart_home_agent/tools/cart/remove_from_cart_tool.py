from google.adk.tools import ToolContext

from smart_home_agent.tools._base import ToolResult, tool_errors
from smart_home_agent.tools.cart._cart_tool import CartTool


class RemoveFromCartTool(CartTool):
    @tool_errors
    def remove_from_cart(
        self, product_ids: list[str], tool_context: ToolContext, quantities: list[int] | None = None
    ) -> ToolResult:
        """Remove one or more products from the customer's shopping cart in a single change. The interface
        asks the customer to confirm the whole change first; it only happens when the result status is "ok".

        Args:
          product_ids: The 8-digit catalog ids of products in the cart.
          quantities: Units to remove per product (1-99), in the same order as product_ids; 0 removes all
            units of that product. Omit it to remove the listed products completely.
        """
        return self.change(tool_context, "remove", product_ids, quantities)
