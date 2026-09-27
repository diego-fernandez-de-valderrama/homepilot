from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.tools.cart._central_unit_check import CentralUnitCheck


class AddConfirmationRule:
    """ADK `require_confirmation` for add_to_cart (`needs_confirmation`): every add waits for the customer, except
    one that the tool refuses at once because it would put several central units into the cart (nothing to
    confirm)."""

    def __init__(self, services: Services) -> None:
        self._central_units = CentralUnitCheck(services)

    def needs_confirmation(
        self, product_ids: list[str], tool_context: ToolContext, quantities: list[int] | None = None
    ) -> bool:
        return not self._central_units.refused(tool_context, product_ids, quantities)
