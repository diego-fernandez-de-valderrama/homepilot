import asyncio

from google.adk.events import Event, EventActions

from smart_home_agent.agent._session_store import SessionStore
from smart_home_agent.agent._turn_collector import ConfirmationRequest
from smart_home_agent.models.cart import CartConfirmation, CartView
from smart_home_agent.services.cart import CartService
from smart_home_agent.session import STATE_KEY, SessionState, read_state
from smart_home_agent.tools import CONFIRMED_TOOLS


class CustomerCart:
    """The cart as the interface sees it, without any model call: view, the customer's own edits, and the pending
    cart changes of a turn described for the confirmation card."""

    def __init__(self, cart: CartService | None, sessions: SessionStore) -> None:
        self._cart = cart
        self._sessions = sessions

    async def view(self, session_id: str, user_id: str) -> CartView:
        if self._cart is None:
            return CartView()
        items = (await self._sessions.session_state(session_id, user_id)).cart
        return await asyncio.to_thread(self._cart.view, items) if items else CartView()

    async def set_quantity(self, session_id: str, product_id: str, quantity: int, user_id: str) -> None:
        """The customer's own edit in the interface (0 removes the line). It is recorded as a state-only
        event and flagged, so the next instruction tells the model to call view_cart again."""
        if self._cart is None:
            raise RuntimeError("AgentService was created without a cart service.")
        cart = self._cart
        async with self._sessions.lock(session_id, user_id):  # never interleaved with a running turn of this session
            session = await self._sessions.get_or_create(session_id, user_id)
            current = read_state(session.state)
            current.cart = await asyncio.to_thread(cart.set_quantity, current.cart, product_id, quantity)
            current.cart_changed_by_user = True
            event = Event(
                author="user",
                invocation_id=Event.new_id(),
                actions=EventActions(state_delta={STATE_KEY: current.model_dump(mode="json")}),
            )
            await self._sessions.append_event(session, event)

    async def describe(self, requests: list[ConfirmationRequest], session: SessionState) -> list[CartConfirmation]:
        if not requests or self._cart is None:
            return []
        cart = self._cart
        return await asyncio.to_thread(
            lambda: [cart.describe(rid, CONFIRMED_TOOLS[name], args, session.cart) for rid, name, args in requests]
        )
