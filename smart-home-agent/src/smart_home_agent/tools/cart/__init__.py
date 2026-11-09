"""Shopping cart tools. The customer can only fill the cart through the agent, and every add or remove waits
for the customer's confirmation in the interface (ADK tool confirmation, set up in `ToolRegistry`).

- `ViewCartTool` (`view_cart`): the current cart with catalog prices.
- `AddToCartTool` (`add_to_cart`) and `RemoveFromCartTool` (`remove_from_cart`): the tools in `CONFIRMED_TOOLS`.
- `CartConfirmationRule`: the add's and remove's `require_confirmation` callable.
- `CartResultCallback` (`after_tool_callback`): the result of an add/remove ADK answered itself.

One add/remove call can cover several products, so the customer confirms them together; the change is
applied all or nothing. Add and remove always tell the model whether the change happened, what is left of
each product and what is left in the cart, also when it failed or the customer cancelled it
(`CartResultCallback` covers the calls the tool never ran).

A change the tool would reject (invalid arguments, a product not in the catalog for an add or not in the cart for
a removal) is never shown to the customer either: the tool answers at once, and its message tells the model to
fix the call and call the tool again in the same turn without mentioning it, so a made-up id never reaches a
confirmation card.

An add that would put more than one unit of a hub, gateway, bridge, controller or starter set into the cart
(`CartService.central_units_over_one`) is not shown to the customer for confirmation: the tool answers at once
with "needs_clarification", so the model asks whether one unit is enough. The same add is allowed in a later turn,
after the customer answered (`SessionState.central_units_asked`). There is no tool parameter for it on purpose:
an extra add_to_cart parameter changed how the model handled unrelated requests.
"""

from smart_home_agent.tools.cart.add_to_cart_tool import AddToCartTool
from smart_home_agent.tools.cart.cart_confirmation_rule import CartConfirmationRule
from smart_home_agent.tools.cart.cart_result_callback import CartResultCallback
from smart_home_agent.tools.cart.confirmed_tools import CONFIRMED_TOOLS
from smart_home_agent.tools.cart.remove_from_cart_tool import RemoveFromCartTool
from smart_home_agent.tools.cart.view_cart_tool import ViewCartTool

__all__ = [
    "CONFIRMED_TOOLS",
    "AddToCartTool",
    "CartConfirmationRule",
    "CartResultCallback",
    "RemoveFromCartTool",
    "ViewCartTool",
]
