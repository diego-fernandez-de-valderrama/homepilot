from typing import Any

from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.models import CartAction
from smart_home_agent.services import CartChangeError
from smart_home_agent.session import SessionState, StateStore
from smart_home_agent.tools._base import HomePilotTool, ToolResult
from smart_home_agent.tools.cart._change_report import ChangeReport


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
        try:
            changes = cart.changes(action, product_ids, quantities)
            session.cart = cart.apply(session.cart, action, changes)
        except CartChangeError as exc:  # nothing applied: the customer confirmed the change as a whole
            StateStore.save(tool_context, session)
            message = "Nothing was changed: " + str(exc)
            return ChangeReport.build(exc.status, action, ids, before, before, message, exc.errors, catalog)
        except ValueError as exc:
            StateStore.save(tool_context, session)
            message = f"Nothing was changed: {exc}"
            return ChangeReport.build("invalid_input", action, ids, before, before, message, catalog=catalog)
        StateStore.save(tool_context, session)
        return ChangeReport.build("ok", action, ids, before, cart.view(session.cart), catalog=catalog)
