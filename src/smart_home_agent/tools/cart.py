"""Shopping cart tools. The customer can only fill the cart through the agent, and every add or remove waits
for the customer's confirmation in the interface (ADK tool confirmation, set up in `build_tools`).

One add/remove call can cover several products, so the customer confirms them together; the change is
applied all or nothing. Add and remove always tell the model whether the change happened, what is left of
each product and what is left in the cart, also when it failed or the customer cancelled it
(`cart_result_callback` covers the calls the tool never ran).

An add that would put more than one unit of a hub, gateway, bridge, controller or starter set into the cart
(`CartService.central_units_over_one`) is not shown to the customer for confirmation: the tool answers at once
with "needs_clarification", so the model asks whether one unit is enough. The same add is allowed in a later turn,
after the customer answered (`SessionState.central_units_asked`). There is no tool parameter for it on purpose:
an extra add_to_cart parameter changed how the model handled unrelated requests.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from google.adk.tools import BaseTool, ToolContext

from smart_home_agent.agent import state
from smart_home_agent.agent.state import CentralUnitsAsked, SessionState
from smart_home_agent.container import Services
from smart_home_agent.models.cart import CartAction, CartView
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services.cart import CartChangeError
from smart_home_agent.tools._common import ToolResult, ok, tool_errors

CONFIRMED_TOOLS: dict[str, CartAction] = {"add_to_cart": "add", "remove_from_cart": "remove"}

_AWAITING = "The customer is asked to confirm this change in the interface. It is not applied yet."
_REJECTED = "The customer cancelled this change in the interface. The cart was not changed."
_CENTRAL_UNITS = (
    "Nothing was changed and the customer was not asked yet: one hub, gateway, bridge, controller or starter set "
    "usually runs all devices of a home. Ask the customer whether one unit is enough. Only if they answer that "
    "they want several, call add_to_cart again with the same quantities."
)


def _synced(tool_context: ToolContext) -> SessionState:
    """Every cart tool returns the current cart, so the model is up to date with the interface again."""
    session = state.load(tool_context)
    session.cart_checked = True
    session.cart_changed_by_user = False
    return session


def _ids(product_ids: Any) -> list[str]:
    return list(dict.fromkeys(str(pid).strip() for pid in product_ids or [] if str(pid).strip()))


def change_result(
    status: str,
    action: CartAction,
    product_ids: list[str],
    before: CartView,
    after: CartView,
    message: str | None = None,
    errors: list[dict[str, str]] | None = None,
    catalog: CatalogReader | None = None,
) -> ToolResult:
    """Outcome of an add or remove: success or failure, per product the units changed and the units left
    (or a note that none are left), and the remaining cart lines (or a note that the cart is empty).
    `catalog` names the products that are in neither cart view (an add waiting for confirmation)."""
    products = {line.product_id: line.product for line in after.lines + before.lines if line.product}
    missing = [pid for pid in product_ids if pid not in products]
    if catalog is not None and missing:
        products.update({p.id: p for p in catalog.get_products(missing)})
    changes = []
    for pid in product_ids:
        remaining = after.quantity_of(pid)
        product = products.get(pid)
        change: dict[str, Any] = {
            "product_id": pid,
            "title": product.title if product else None,
            "variant": product.variant if product else None,
            "subtitle": product.subtitle if product else None,
            "quantity_changed": abs(remaining - before.quantity_of(pid)),
            "remaining_of_product": remaining,
        }
        if remaining == 0:
            change["note"] = "none of this product left in the cart"
        changes.append(change)
    result: ToolResult = {
        "status": status,
        "action": action,
        "changes": changes,
        "remaining_items": after.for_model(),
        "cart_total": after.total,
    }
    if not after.lines:
        result["note"] = "the cart is empty"
    if message:
        result["message"] = message
    if errors:
        result["errors"] = errors
    return result


def _refused_central_units(
    services: Services, tool_context: ToolContext, product_ids: list[str], quantities: list[int] | None
) -> list[dict[str, Any]]:
    """Hubs, gateways, controllers and starter sets the add would put in the cart more than once, unless that
    was refused in an earlier turn (the customer has answered since). Invalid arguments give none here: the tool
    itself reports them."""
    try:
        changes = services.cart.changes("add", product_ids, quantities)
    except (ValueError, TypeError):
        return []
    session = state.load(tool_context)
    over = services.cart.central_units_over_one(session.cart, changes)
    asked = session.central_units_asked
    if asked is not None and asked.invocation_id != tool_context.invocation_id:
        over = [(p, units) for p, units in over if units > asked.units.get(p.id, 0)]
    return [{"product_id": p.id, "title": p.title, "units_in_cart_after": units} for p, units in over]


def make_add_confirmation_rule(services: Services) -> Callable[..., bool]:
    """ADK `require_confirmation` for add_to_cart: every add waits for the customer, except one that the tool
    refuses at once because it would put several central units into the cart (nothing to confirm)."""

    def add_needs_confirmation(
        product_ids: list[str], tool_context: ToolContext, quantities: list[int] | None = None
    ) -> bool:
        return not _refused_central_units(services, tool_context, product_ids, quantities)

    return add_needs_confirmation


def make_view_cart(services: Services):
    @tool_errors
    def view_cart(tool_context: ToolContext) -> ToolResult:
        """List the products in the customer's shopping cart of this conversation, with quantities and
        catalog prices. Call it at the start of a conversation and whenever you are told the customer changed
        the cart in the interface.
        """
        session = _synced(tool_context)
        view = services.cart.view(session.cart)
        state.save(tool_context, session)
        result = ok(items=view.for_model(), item_count=view.item_count, cart_total=view.total)
        if not view.lines:
            result["note"] = "the cart is empty"
        if view.has_unpriced:
            result["unpriced_note"] = "some products have no listed price and are not in the total"
        return result

    return view_cart


def _change_cart(
    services: Services,
    tool_context: ToolContext,
    action: CartAction,
    product_ids: list[str],
    quantities: list[int] | None,
) -> ToolResult:
    session = _synced(tool_context)
    before = services.cart.view(session.cart)
    ids = _ids(product_ids)
    try:
        changes = services.cart.changes(action, product_ids, quantities)
        session.cart = services.cart.apply(session.cart, action, changes)
    except CartChangeError as exc:  # nothing applied: the customer confirmed the change as a whole
        state.save(tool_context, session)
        message = "Nothing was changed: " + str(exc)
        return change_result(exc.status, action, ids, before, before, message, exc.errors, services.catalog)
    except ValueError as exc:
        state.save(tool_context, session)
        message = f"Nothing was changed: {exc}"
        return change_result("invalid_input", action, ids, before, before, message, catalog=services.catalog)
    state.save(tool_context, session)
    return change_result("ok", action, ids, before, services.cart.view(session.cart), catalog=services.catalog)


def make_add_to_cart(services: Services):
    @tool_errors
    def add_to_cart(
        product_ids: list[str], tool_context: ToolContext, quantities: list[int] | None = None
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
        if over := _refused_central_units(services, tool_context, product_ids, quantities):
            session = _synced(tool_context)
            session.central_units_asked = CentralUnitsAsked(
                invocation_id=tool_context.invocation_id,
                units={unit["product_id"]: unit["units_in_cart_after"] for unit in over},
            )
            state.save(tool_context, session)
            view = services.cart.view(session.cart)
            result = change_result(
                "needs_clarification", "add", _ids(product_ids), view, view, _CENTRAL_UNITS, catalog=services.catalog
            )
            result["central_units"] = over
            return result
        return _change_cart(services, tool_context, "add", product_ids, quantities)

    return add_to_cart


def make_remove_from_cart(services: Services):
    @tool_errors
    def remove_from_cart(
        product_ids: list[str], tool_context: ToolContext, quantities: list[int] | None = None
    ) -> ToolResult:
        """Remove one or more products from the customer's shopping cart in a single change. The interface
        asks the customer to confirm the whole change first; it only happens when the result status is "ok".

        Args:
          product_ids: The 8-digit catalog ids of products in the cart.
          quantities: Units to remove per product (1-99), in the same order as product_ids; 0 removes all
            units of that product. Omit it to remove the listed products completely.
        """
        return _change_cart(services, tool_context, "remove", product_ids, quantities)

    return remove_from_cart


def make_cart_result_callback(
    services: Services,
) -> Callable[[BaseTool, dict[str, Any], ToolContext, dict[str, Any]], Awaitable[dict[str, Any] | None]]:
    """`after_tool_callback`: ADK answers an unconfirmed or cancelled add/remove itself, without running the
    tool. Its generic error is replaced by the same result shape the tool returns, with the unchanged cart."""

    async def cart_result(
        tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: dict[str, Any]
    ) -> dict[str, Any] | None:
        action = CONFIRMED_TOOLS.get(tool.name)
        confirmation = tool_context.tool_confirmation
        if action is None or (confirmation is not None and confirmation.confirmed):
            return None  # not a cart change, or the tool really ran and built its own result
        if confirmation is None and tool_response.get("status") == "needs_clarification":
            return None  # the add refused several central units at once, without asking the customer
        session = _synced(tool_context)
        state.save(tool_context, session)
        status, message = ("awaiting_confirmation", _AWAITING) if confirmation is None else ("rejected", _REJECTED)
        ids = _ids(args.get("product_ids"))

        def build() -> dict[str, Any]:  # database reads: off the shared agent event loop
            view = services.cart.view(session.cart)
            return change_result(status, action, ids, view, view, message, catalog=services.catalog)

        return await asyncio.to_thread(build)

    return cart_result
