from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.models import CartAction
from smart_home_agent.session import StateStore
from smart_home_agent.tools.cart._central_unit_check import CentralUnitCheck


class CartConfirmationRule:
    """ADK `require_confirmation` for add_to_cart and remove_from_cart (`needs_confirmation`): every change waits
    for the customer, except one the tool refuses at once (nothing to confirm): invalid arguments, a product not
    in the catalog (add) or not in the cart (remove), or an add that would put several central units into the
    cart. The customer never sees such a call, so the model can fix it and call the tool again."""

    def __init__(self, services: Services, action: CartAction) -> None:
        self._services = services
        self._action = action
        self._central_units = CentralUnitCheck(services)

    def needs_confirmation(
        self, product_ids: list[str], tool_context: ToolContext, quantities: list[int] | None = None
    ) -> bool:
        cart = self._services.cart
        try:
            changes = cart.changes(self._action, product_ids, quantities)
        except (ValueError, TypeError):
            return False
        if cart.problems(StateStore.load(tool_context).cart, self._action, changes):
            return False
        return self._action != "add" or not self._central_units.refused(tool_context, product_ids, quantities)
