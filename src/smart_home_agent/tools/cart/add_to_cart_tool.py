from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.session import CentralUnitsAsked, save_state
from smart_home_agent.tools._base import ToolResult, tool_errors
from smart_home_agent.tools.cart._cart_tool import CartTool
from smart_home_agent.tools.cart._central_unit_check import CentralUnitCheck
from smart_home_agent.tools.cart._change_report import ChangeReport

_CENTRAL_UNITS = (
    "Nothing was changed and the customer was not asked yet: one hub, gateway, bridge, controller or starter set "
    "usually runs all devices of a home. Ask the customer whether one unit is enough. Only if they answer that "
    "they want several, call add_to_cart again with the same quantities."
)


class AddToCartTool(CartTool):
    def __init__(self, services: Services) -> None:
        super().__init__(services)
        self._central_units = CentralUnitCheck(services)

    @tool_errors
    def add_to_cart(
        self, product_ids: list[str], tool_context: ToolContext, quantities: list[int] | None = None
    ) -> ToolResult:
        """Add one or more catalog products to the customer's shopping cart in a single change. The interface
        asks the customer to confirm the whole change first; it only happens when the result status is "ok".
        When the customer wants several products, put them all in one call so they confirm once.
        Only call it for products the customer asked to add or buy, or whose offer they accepted.

        Args:
          product_ids: The 8-digit catalog ids from tool results in this conversation.
          quantities: Units to add per product (1-99), in the same order as product_ids. Omit it to add
            1 of each. To raise a quantity from 2 to 3, add 1.
        """
        if over := self._central_units.refused(tool_context, product_ids, quantities):
            session = self.synced_state(tool_context)
            session.central_units_asked = CentralUnitsAsked(
                invocation_id=tool_context.invocation_id,
                units={unit["product_id"]: unit["units_in_cart_after"] for unit in over},
            )
            save_state(tool_context, session)
            view = self._services.cart.view(session.cart)
            ids = self.product_ids(product_ids)
            result = ChangeReport.build(
                "needs_clarification", "add", ids, view, view, _CENTRAL_UNITS, catalog=self._services.catalog
            )
            result["central_units"] = over
            return result
        return self.change(tool_context, "add", product_ids, quantities)
