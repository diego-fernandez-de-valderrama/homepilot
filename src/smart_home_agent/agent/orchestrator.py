"""Single ADK agent (no multi-agent) plus a small synchronous facade for the UI."""

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.events import Event, EventActions
from google.adk.flows.llm_flows.functions import REQUEST_CONFIRMATION_FUNCTION_CALL_NAME
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.tools import FunctionTool
from google.genai import types

from smart_home_agent.agent.language import detect_language
from smart_home_agent.agent.model import ResilientGemini, http_retry_options
from smart_home_agent.agent.prompts import BASE_INSTRUCTION, MEMORY_INSTRUCTION, build_instruction
from smart_home_agent.agent.state import (
    GUARDRAIL_KEY,
    PROFILE_KEY,
    STATE_KEY,
    TURN_LANGUAGE_KEY,
    SessionState,
    read_state,
)
from smart_home_agent.agent.trace import AgentReply, TurnTrace
from smart_home_agent.config import Settings
from smart_home_agent.container import Services
from smart_home_agent.guardrail.callbacks import GuardrailReport, make_input_callback, make_output_callback
from smart_home_agent.guardrail.classifier import SemanticGuardrail
from smart_home_agent.guardrail.output_check import OutputValidator
from smart_home_agent.models.cart import CartConfirmation, CartView
from smart_home_agent.models.profile import CustomerProfile
from smart_home_agent.models.rich import RichContent
from smart_home_agent.services.cart import CartService
from smart_home_agent.services.profile import ProfileService
from smart_home_agent.services.rich_content import RichContentService
from smart_home_agent.tools import CONFIRMED_TOOLS, build_tools
from smart_home_agent.tools.cart import make_cart_result_callback

logger = logging.getLogger(__name__)

AGENT_NAME = "homepilot"
DEFAULT_USER = "customer"


# Verbatim instruction lines long enough that quoting them in an answer can only be a prompt leak.
_MIN_LEAK_LINE = 60


def _leak_markers(tools: list[FunctionTool]) -> list[str]:
    lines = [line.strip(" -") for line in (BASE_INSTRUCTION + MEMORY_INSTRUCTION).splitlines()]
    return [tool.name for tool in tools] + [line for line in lines if len(line) >= _MIN_LEAK_LINE]


def build_agent(
    services: Services, settings: Settings, guardrail: SemanticGuardrail | None = None, model: Any = None
) -> LlmAgent:
    """Builds the agent without any network call (the Gemini client is created lazily).

    The guardrail wraps the unchanged agent through ADK callbacks: the semantic input check runs
    before the model (only when a `guardrail` is given and AGENT_GUARDRAIL_ENABLED is true) and the
    deterministic output check after it (AGENT_GUARDRAIL_OUTPUT_CHECK). `model` replaces the Gemini
    model (tests only).
    """
    if model is None:
        api_key = settings.gemini.api_key.get_secret_value() if settings.gemini.api_key else None
        options = settings.agent
        model = ResilientGemini(
            model=options.model,
            client_kwargs={"api_key": api_key} if api_key else None,
            retry_options=http_retry_options(
                options.model_retries, options.model_retry_initial_delay, options.model_retry_max_delay
            ),
            empty_retries=options.model_retries,
            retry_initial_delay=options.model_retry_initial_delay,
            retry_max_delay=options.model_retry_max_delay,
        )
    tools = build_tools(services)
    input_guardrail = guardrail if settings.agent.guardrail_enabled else None
    validator = (
        OutputValidator(services.catalog, input_guardrail, _leak_markers(tools))
        if settings.agent.guardrail_output_check
        else None
    )
    return LlmAgent(
        name=AGENT_NAME,
        description="Smart home product advisor backed by the HomePilot catalog.",
        model=model,
        instruction=build_instruction,
        tools=tools,
        generate_content_config=types.GenerateContentConfig(
            temperature=settings.agent.temperature,
            thinking_config=(
                types.ThinkingConfig(thinking_budget=settings.agent.thinking_budget)
                if settings.agent.thinking_budget != -1
                else None
            ),
        ),
        before_agent_callback=make_input_callback(input_guardrail) if input_guardrail else None,
        after_model_callback=make_output_callback(validator) if validator else None,
        after_tool_callback=make_cart_result_callback(services),
    )


class AgentService:
    """Runs conversation turns. Sessions live in memory for the lifetime of the process.

    All turns run on one long-lived event loop (in a background thread): ADK caches its Gemini
    client per loop, so a new loop per turn (`asyncio.run`) would leave clients bound to closed loops.

    With `rich_content`, the presentation tags of each answer are resolved to catalog data (`AgentReply.rich`).

    Cart changes (add_to_cart / remove_from_cart) pause the turn until the customer decides: the reply lists
    them in `pending_confirmations` and `confirm` answers them, which runs (or cancels) the tools and lets
    the model continue. The interface reads and edits the cart through `cart` / `set_cart_quantity`
    without any model call; an edit sets `cart_changed_by_user`, so the prompt tells the model to look again.

    With `profiles`, the customer's stored facts (per `user_id`, across conversations) are loaded before every
    turn into the state, where the instruction shows them. A memory failure never blocks the turn.
    """

    def __init__(
        self,
        agent: LlmAgent,
        app_name: str,
        rich_content: RichContentService | None = None,
        cart: CartService | None = None,
        profiles: ProfileService | None = None,
    ) -> None:
        self._app_name = app_name
        self._rich_content = rich_content
        self._cart = cart
        self._profiles = profiles
        self._sessions = InMemorySessionService()
        self._runner = Runner(app_name=app_name, agent=agent, session_service=self._sessions, auto_create_session=True)
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, name="homepilot-agent-loop", daemon=True).start()

    def _run[T](self, coroutine: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()

    def chat(self, session_id: str, text: str, user_id: str = DEFAULT_USER) -> AgentReply:
        return self._run(self.chat_async(session_id, text, user_id))

    def submit(
        self,
        session_id: str,
        text: str,
        user_id: str = DEFAULT_USER,
        on_tool_call: Callable[[str], None] | None = None,
    ) -> Future[AgentReply]:
        """Starts a turn without blocking. `on_tool_call` receives each tool name as the model calls it
        (on the agent loop thread, so it must be thread-safe), which lets a UI show real progress."""
        return asyncio.run_coroutine_threadsafe(self.chat_async(session_id, text, user_id, on_tool_call), self._loop)

    def state(self, session_id: str, user_id: str = DEFAULT_USER) -> SessionState:
        return self._run(self.state_async(session_id, user_id))

    def confirm(self, session_id: str, decisions: dict[str, bool], user_id: str = DEFAULT_USER) -> AgentReply:
        return self._run(self.confirm_async(session_id, decisions, user_id))

    def submit_confirmation(
        self,
        session_id: str,
        decisions: dict[str, bool],
        user_id: str = DEFAULT_USER,
        on_tool_call: Callable[[str], None] | None = None,
    ) -> Future[AgentReply]:
        """Like `submit`, for the customer's decisions on the pending cart changes of the previous reply."""
        return asyncio.run_coroutine_threadsafe(
            self.confirm_async(session_id, decisions, user_id, on_tool_call), self._loop
        )

    async def chat_async(
        self,
        session_id: str,
        text: str,
        user_id: str = DEFAULT_USER,
        on_tool_call: Callable[[str], None] | None = None,
    ) -> AgentReply:
        language = detect_language(text)
        message = types.Content(role="user", parts=[types.Part(text=text)])
        state_delta = {TURN_LANGUAGE_KEY: language, GUARDRAIL_KEY: None}
        return await self._turn(session_id, user_id, message, state_delta, language, on_tool_call)

    async def confirm_async(
        self,
        session_id: str,
        decisions: dict[str, bool],
        user_id: str = DEFAULT_USER,
        on_tool_call: Callable[[str], None] | None = None,
    ) -> AgentReply:
        """Answers ADK's confirmation requests (request id -> confirmed). A message without text: the input
        guardrail skips it and the reply language of the previous message stays."""
        parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    id=request_id, name=REQUEST_CONFIRMATION_FUNCTION_CALL_NAME, response={"confirmed": confirmed}
                )
            )
            for request_id, confirmed in decisions.items()
        ]
        message = types.Content(role="user", parts=parts)
        return await self._turn(session_id, user_id, message, {GUARDRAIL_KEY: None}, None, on_tool_call)

    async def _turn(
        self,
        session_id: str,
        user_id: str,
        message: types.Content,
        state_delta: dict[str, Any],
        language: str | None,
        on_tool_call: Callable[[str], None] | None,
    ) -> AgentReply:
        if (profile := await self._profile_snapshot(user_id)) is not None:
            state_delta = {**state_delta, PROFILE_KEY: profile}
        trace = TurnTrace()
        answer: list[str] = []
        requests: list[tuple[str, str, dict[str, Any]]] = []  # (request id, tool name, tool args)
        errors: list[str] = []
        events = self._runner.run_async(
            user_id=user_id, session_id=session_id, new_message=message, state_delta=state_delta
        )
        async for event in events:
            for call in event.get_function_calls():
                if call.name == REQUEST_CONFIRMATION_FUNCTION_CALL_NAME:
                    original = (call.args or {}).get("originalFunctionCall") or {}
                    if call.id and original.get("name") in CONFIRMED_TOOLS:
                        requests.append((call.id, original["name"], dict(original.get("args") or {})))
                    continue
                trace.add_call(call.id, call.name or "", dict(call.args or {}))
                if on_tool_call is not None:
                    on_tool_call(call.name or "")
            for response in event.get_function_responses():
                trace.add_response(response.id, response.name or "", response.response)
            if event.is_final_response() and event.content and event.content.parts:
                answer.extend(part.text for part in event.content.parts if part.text and not part.thought)
            if event.error_message:
                logger.warning("agent error event: %s", event.error_message)
                errors.append(event.error_message)
        session = await self._sessions.get_session(app_name=self._app_name, user_id=user_id, session_id=session_id)
        state = session.state if session else {}
        report = state.get(GUARDRAIL_KEY)
        reply_text = "".join(answer).strip()
        session_state = read_state(state)
        profile = state.get(PROFILE_KEY)
        return AgentReply(
            text=reply_text,
            detected_language=language,
            trace=trace,
            state=session_state,
            guardrail=GuardrailReport.model_validate(report) if report else None,
            rich=await self._resolve_rich(reply_text, session_state),
            pending_confirmations=await self._describe(requests, session_state),
            profile=CustomerProfile.model_validate(profile) if profile else None,
            error="; ".join(errors) or None,
        )

    async def _describe(
        self, requests: list[tuple[str, str, dict[str, Any]]], session: SessionState
    ) -> list[CartConfirmation]:
        if not requests or self._cart is None:
            return []
        cart = self._cart
        return await asyncio.to_thread(
            lambda: [cart.describe(rid, CONFIRMED_TOOLS[name], args, session.cart) for rid, name, args in requests]
        )

    async def _resolve_rich(self, text: str, session: SessionState) -> RichContent | None:
        if self._rich_content is None or not text:
            return None
        try:
            return await asyncio.to_thread(
                self._rich_content.resolve, text, session.must_support, session.owned_devices, session.last_upsell
            )
        except Exception:  # the answer is still shown, as plain text without the components
            logger.warning("rich content: resolving the answer's tags failed", exc_info=True)
            return None

    async def _profile_snapshot(self, user_id: str) -> dict[str, Any] | None:
        profiles = self._profiles
        if profiles is None:
            return None
        try:
            profile = await asyncio.to_thread(profiles.profile, user_id, True)  # retracted: "no longer ..."
            return profile.model_dump(mode="json")
        except Exception:  # fail open: the turn runs with the previous snapshot, if any
            logger.warning("customer memory: loading the profile of %r failed", user_id, exc_info=True)
            return None

    def profile(self, user_id: str = DEFAULT_USER, include_retracted: bool = True) -> CustomerProfile | None:
        """Everything stored about the customer, live from the memory database (None without memory)."""
        if self._profiles is None:
            return None
        return self._profiles.profile(user_id, include_retracted)

    async def state_async(self, session_id: str, user_id: str = DEFAULT_USER) -> SessionState:
        session = await self._sessions.get_session(app_name=self._app_name, user_id=user_id, session_id=session_id)
        return read_state(session.state) if session else SessionState()

    # ---------- Cart access for the interface (no model call) ----------

    def cart(self, session_id: str, user_id: str = DEFAULT_USER) -> CartView:
        return self._run(self.cart_async(session_id, user_id))

    def set_cart_quantity(self, session_id: str, product_id: str, quantity: int, user_id: str = DEFAULT_USER) -> None:
        self._run(self.set_cart_quantity_async(session_id, product_id, quantity, user_id))

    async def cart_async(self, session_id: str, user_id: str = DEFAULT_USER) -> CartView:
        if self._cart is None:
            return CartView()
        items = (await self.state_async(session_id, user_id)).cart
        return await asyncio.to_thread(self._cart.view, items) if items else CartView()

    async def set_cart_quantity_async(
        self, session_id: str, product_id: str, quantity: int, user_id: str = DEFAULT_USER
    ) -> None:
        """The customer's own edit in the interface (0 removes the line). It is recorded as a state-only
        event and flagged, so the next instruction tells the model to call view_cart again."""
        if self._cart is None:
            raise RuntimeError("AgentService was created without a cart service.")
        session = await self._session(session_id, user_id)
        current = read_state(session.state)
        current.cart = self._cart.set_quantity(current.cart, product_id, quantity)
        current.cart_changed_by_user = True
        event = Event(
            author="user",
            invocation_id=Event.new_id(),
            actions=EventActions(state_delta={STATE_KEY: current.model_dump(mode="json")}),
        )
        await self._sessions.append_event(session, event)

    async def _session(self, session_id: str, user_id: str) -> Session:
        session = await self._sessions.get_session(app_name=self._app_name, user_id=user_id, session_id=session_id)
        if session is None:
            session = await self._sessions.create_session(
                app_name=self._app_name, user_id=user_id, session_id=session_id
            )
        return session
