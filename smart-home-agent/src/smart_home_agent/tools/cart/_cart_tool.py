from typing import Any

from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.models import CartAction
from smart_home_agent.services import CartChangeError
from smart_home_agent.session import SessionState, StateStore
from smart_home_agent.tools._base import HomePilotTool, ToolResult
from smart_home_agent.tools.cart._change_report import ChangeReport

_UNSEEN = (
    "The customer was not shown this change, so do not mention this error to them. Fix the call and call {tool} "
    "again now with every product of the request: {fix} Only if a product cannot be found, tell the customer."
)
_RETRY: dict[CartAction, str] = {
    "add": _UNSEEN.format(
        tool="add_to_cart",
        fix="use only 8-digit ids from tool results in this conversation; for a product without such an id "
        "(e.g. a hub), call search_products first.",
    ),
    "remove": _UNSEEN.format(
        tool="remove_from_cart", fix="use only product ids that are in the cart (call view_cart to see them)."
    ),
}


class CartTool(HomePilotTool):
    """Base of the cart tools (and the helpers `CartResultCallback` shares): the session sync after every cart
    call and the all-or-nothing add/remove."""

    def __init__(self, services: Services) -> None:
        self._services = services

    @staticmethod
    def synced_state(tool_context: ToolContext) -> SessionState:
        """Every cart tool returns the current cart, so the model is up to date with the interface again."""
        session = StateStore.load(tool_context)
        session.cart_checked = True
        session.cart_changed_by_user = False
        return session

    @staticmethod
    def product_ids(raw: Any) -> list[str]:
        return list(dict.fromkeys(str(pid).strip() for pid in raw or [] if str(pid).strip()))

    def change(
        self, tool_context: ToolContext, action: CartAction, product_ids: list[str], quantities: list[int] | None
    ) -> ToolResult:
        cart, catalog = self._services.cart, self._services.catalog
        session = self.synced_state(tool_context)
        before = cart.view(session.cart)
        ids = self.product_ids(product_ids)
        # Without a confirmation the customer never saw this call (CartConfirmationRule refused it at once):
        # nothing is applied, and the model is told to fix the call instead of explaining it.
        unseen = tool_context.tool_confirmation is None
        try:
            changes = cart.changes(action, product_ids, quantities)
            if unseen and (errors := cart.problems(session.cart, action, changes)):
                raise CartChangeError(errors)
            if unseen:
                raise ValueError("this change was not confirmed by the customer.")
            session.cart = cart.apply(session.cart, action, changes)
        except CartChangeError as exc:  # nothing applied: the customer confirmed the change as a whole
            StateStore.save(tool_context, session)
            message = self._failure(action, str(exc), unseen)
            return ChangeReport.build(exc.status, action, ids, before, before, message, exc.errors, catalog)
        except ValueError as exc:
            StateStore.save(tool_context, session)
            message = self._failure(action, str(exc), unseen)
            return ChangeReport.build("invalid_input", action, ids, before, before, message, catalog=catalog)
        StateStore.save(tool_context, session)
        return ChangeReport.build("ok", action, ids, before, cart.view(session.cart), catalog=catalog)

    @staticmethod
    def _failure(action: CartAction, reason: str, unseen: bool) -> str:
        if not unseen:
            return f"Nothing was changed: {reason}"
        return f"Nothing was changed: {reason.rstrip('.')}. {_RETRY[action]}"
