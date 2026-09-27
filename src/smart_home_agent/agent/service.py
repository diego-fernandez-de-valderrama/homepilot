from collections.abc import Callable
from concurrent.futures import Future

from google.adk.agents import LlmAgent
from google.adk.runners import Runner

from smart_home_agent.agent._confirmation_ledger import ConfirmationLedger
from smart_home_agent.agent._customer_cart import CustomerCart
from smart_home_agent.agent._event_loop import EventLoopThread
from smart_home_agent.agent._profile_loader import ProfileLoader
from smart_home_agent.agent._session_store import SessionStore
from smart_home_agent.agent._turn_runner import TurnRunner
from smart_home_agent.agent.constants import DEFAULT_USER
from smart_home_agent.agent.reply import AgentReply
from smart_home_agent.models import CartView, CustomerProfile
from smart_home_agent.services.cart import CartService
from smart_home_agent.services.profile import ProfileService
from smart_home_agent.services.rich_content import RichContentService
from smart_home_agent.session import SessionState


class AgentService:
    """Synchronous entry point of the agent for the interface and the CLI. Sessions live in memory for the
    lifetime of the process; every call runs on one background event loop (`EventLoopThread`).

    - `chat` / `submit` run a turn for a customer message (`TurnRunner`).
    - Cart changes (add_to_cart / remove_from_cart) pause the turn until the customer decides: the reply lists
      them in `pending_confirmations`, and `confirm` / `submit_confirmation` answer them, which runs (or cancels)
      the tools and lets the model continue.
    - `cart` / `set_cart_quantity` read and edit the cart without any model call (`CustomerCart`); an edit sets
      `cart_changed_by_user`, so the prompt tells the model to look again.
    - With `rich_content`, the presentation tags of each answer are resolved to catalog data (`AgentReply.rich`).
    - With `profiles`, the customer's stored facts (per `user_id`, across conversations) are loaded before every
      turn into the state, where the instruction shows them (`ProfileLoader`).
    """

    def __init__(
        self,
        agent: LlmAgent,
        app_name: str,
        rich_content: RichContentService | None = None,
        cart: CartService | None = None,
        profiles: ProfileService | None = None,
    ) -> None:
        self._sessions = SessionStore(app_name)
        self._profiles = ProfileLoader(profiles)
        self._customer_cart = CustomerCart(cart, self._sessions)
        self._confirmations = ConfirmationLedger(self._sessions)
        runner = Runner(
            app_name=app_name, agent=agent, session_service=self._sessions.service, auto_create_session=True
        )
        self._turns = TurnRunner(
            runner, self._sessions, self._profiles, self._customer_cart, self._confirmations, rich_content
        )
        self._loop = EventLoopThread("homepilot-agent-loop")

    # ---------- Turns ----------

    def chat(self, session_id: str, text: str, user_id: str = DEFAULT_USER) -> AgentReply:
        return self._loop.run(self._turns.chat(session_id, text, user_id))

    def submit(
        self,
        session_id: str,
        text: str,
        user_id: str = DEFAULT_USER,
        on_tool_call: Callable[[str], None] | None = None,
    ) -> Future[AgentReply]:
        """Starts a turn without blocking. `on_tool_call` receives each tool name as the model calls it
        (on the agent loop thread, so it must be thread-safe), which lets a UI show real progress."""
        return self._loop.submit(self._turns.chat(session_id, text, user_id, on_tool_call))

    def confirm(self, session_id: str, decisions: dict[str, bool], user_id: str = DEFAULT_USER) -> AgentReply:
        """Answers the pending cart changes of the previous reply (request id -> confirmed)."""
        return self._loop.run(self._turns.confirm(session_id, decisions, user_id))

    def submit_confirmation(
        self,
        session_id: str,
        decisions: dict[str, bool],
        user_id: str = DEFAULT_USER,
        on_tool_call: Callable[[str], None] | None = None,
    ) -> Future[AgentReply]:
        """Like `submit`, for the customer's decisions on the pending cart changes of the previous reply."""
        return self._loop.submit(self._turns.confirm(session_id, decisions, user_id, on_tool_call))

    def applied_confirmations(self, session_id: str, request_ids: list[str], user_id: str = DEFAULT_USER) -> set[str]:
        """The requests whose cart change already ran, so the interface never offers them again."""
        return self._loop.run(self._confirmations.applied(session_id, request_ids, user_id))

    # ---------- State, cart and memory for the interface (no model call) ----------

    def state(self, session_id: str, user_id: str = DEFAULT_USER) -> SessionState:
        return self._loop.run(self._sessions.session_state(session_id, user_id))

    def cart(self, session_id: str, user_id: str = DEFAULT_USER) -> CartView:
        return self._loop.run(self._customer_cart.view(session_id, user_id))

    def set_cart_quantity(self, session_id: str, product_id: str, quantity: int, user_id: str = DEFAULT_USER) -> None:
        self._loop.run(self._customer_cart.set_quantity(session_id, product_id, quantity, user_id))

    def profile(self, user_id: str = DEFAULT_USER, include_retracted: bool = True) -> CustomerProfile | None:
        """Everything stored about the customer, live from the memory database (None without memory)."""
        return self._profiles.profile(user_id, include_retracted)
