import asyncio
import logging
from collections.abc import Callable
from typing import Any

from google.adk.runners import Runner
from google.genai import types

from smart_home_agent.agent._confirmation_ledger import ConfirmationLedger
from smart_home_agent.agent._customer_cart import CustomerCart
from smart_home_agent.agent._profile_loader import ProfileLoader
from smart_home_agent.agent._session_store import SessionStore
from smart_home_agent.agent._turn_collector import TurnCollector
from smart_home_agent.agent.reply import AgentReply, TurnTrace
from smart_home_agent.guardrail import GuardrailReport
from smart_home_agent.models import CustomerProfile, RichContent
from smart_home_agent.services import RichContentService
from smart_home_agent.session import SessionState, StateKey, StateStore, TurnLanguageDetector

logger = logging.getLogger(__name__)


class TurnRunner:
    """Runs one conversation turn through the ADK runner and turns its events into an `AgentReply`.

    A turn is either a customer message (`chat`) or the customer's decisions on pending cart changes (`confirm`).
    Each runs under the session lock, with the customer's profile snapshot added to the state first.
    """

    def __init__(
        self,
        runner: Runner,
        sessions: SessionStore,
        profiles: ProfileLoader,
        cart: CustomerCart,
        confirmations: ConfirmationLedger,
        rich_content: RichContentService | None,
    ) -> None:
        self._runner = runner
        self._sessions = sessions
        self._profiles = profiles
        self._cart = cart
        self._confirmations = confirmations
        self._rich_content = rich_content

    async def chat(
        self, session_id: str, text: str, user_id: str, on_tool_call: Callable[[str], None] | None = None
    ) -> AgentReply:
        language = TurnLanguageDetector.detect(text)
        message = types.Content(role="user", parts=[types.Part(text=text)])
        state_delta = {StateKey.TURN_LANGUAGE: language, StateKey.GUARDRAIL: None}
        return await self._run(session_id, user_id, message, state_delta, language, on_tool_call)

    async def confirm(
        self,
        session_id: str,
        decisions: dict[str, bool],
        user_id: str,
        on_tool_call: Callable[[str], None] | None = None,
    ) -> AgentReply:
        """Answers ADK's confirmation requests (request id -> confirmed). A message without text: the input
        guardrail skips it and the reply language of the previous message stays.

        A request that was already answered and applied (e.g. by a turn that failed after the tool ran) is
        skipped, so retrying a failed confirmation never applies a cart change twice."""
        applied = await self._confirmations.applied(session_id, list(decisions), user_id)
        decisions = {request_id: ok for request_id, ok in decisions.items() if request_id not in applied}
        if not decisions:
            state = await self._sessions.session_state(session_id, user_id)
            return AgentReply(text="", detected_language=None, trace=TurnTrace(), state=state, error="already applied")
        message = self._confirmations.answer(decisions)
        return await self._run(session_id, user_id, message, {StateKey.GUARDRAIL: None}, None, on_tool_call)

    async def _run(
        self,
        session_id: str,
        user_id: str,
        message: types.Content,
        state_delta: dict[str, Any],
        language: str | None,
        on_tool_call: Callable[[str], None] | None,
    ) -> AgentReply:
        async with self._sessions.lock(session_id, user_id):
            state_delta = await self._with_profile(state_delta, session_id, user_id)
            collector = TurnCollector(on_tool_call)
            events = self._runner.run_async(
                user_id=user_id, session_id=session_id, new_message=message, state_delta=state_delta
            )
            async for event in events:
                collector.add(event)
            return await self._reply(collector, await self._sessions.raw_state(session_id, user_id), language)

    async def _with_profile(self, state_delta: dict[str, Any], session_id: str, user_id: str) -> dict[str, Any]:
        """Adds the customer's profile snapshot, which the instruction shows. A memory failure never blocks the turn."""
        if not self._profiles.enabled:
            return state_delta
        profile = await self._profiles.snapshot(user_id)
        if profile is not None:
            return {**state_delta, StateKey.PROFILE: profile}
        if StateKey.PROFILE not in await self._sessions.raw_state(session_id, user_id):
            # Load failed before any snapshot: the key still marks the memory as enabled, so the prompt
            # keeps its memory rules while the memory tool is offered ("nothing stored" for this turn).
            return {**state_delta, StateKey.PROFILE: None}
        return state_delta

    async def _reply(self, collector: TurnCollector, state: dict[str, Any], language: str | None) -> AgentReply:
        session_state = StateStore.read(state)
        report = state.get(StateKey.GUARDRAIL)
        profile = state.get(StateKey.PROFILE)
        return AgentReply(
            text=collector.answer,
            detected_language=language,
            trace=collector.trace,
            state=session_state,
            guardrail=GuardrailReport.model_validate(report) if report else None,
            rich=await self._resolve_rich(collector.answer, session_state),
            pending_confirmations=await self._cart.describe(collector.confirmation_requests, session_state),
            profile=CustomerProfile.model_validate(profile) if profile else None,
            error=collector.error,
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
