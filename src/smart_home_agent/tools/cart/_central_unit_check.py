from typing import Any

from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.session import StateStore


class CentralUnitCheck:
    """Shared by `AddToCartTool` and `AddConfirmationRule`: an add refused because of several central units is
    answered at once and never shown to the customer for confirmation."""

    def __init__(self, services: Services) -> None:
        self._services = services

    def refused(
        self, tool_context: ToolContext, product_ids: list[str], quantities: list[int] | None
    ) -> list[dict[str, Any]]:
        """Hubs, gateways, controllers and starter sets the add would put in the cart more than once, unless that
        was refused in an earlier turn (the customer has answered since). Invalid arguments give none here: the tool
        itself reports them."""
        cart = self._services.cart
        try:
            changes = cart.changes("add", product_ids, quantities)
        except (ValueError, TypeError):
            return []
        session = StateStore.load(tool_context)
        over = cart.central_units_over_one(session.cart, changes)
        asked = session.central_units_asked
        if asked is not None and asked.invocation_id != tool_context.invocation_id:
            over = [(p, units) for p, units in over if units > asked.units.get(p.id, 0)]
        return [{"product_id": p.id, "title": p.title, "units_in_cart_after": units} for p, units in over]
