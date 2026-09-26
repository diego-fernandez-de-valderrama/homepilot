"""Single ADK agent (no multi-agent) plus a small synchronous facade for the UI."""

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from smart_home_agent.agent.language import detect_language
from smart_home_agent.agent.prompts import BASE_INSTRUCTION, build_instruction
from smart_home_agent.agent.state import GUARDRAIL_KEY, TURN_LANGUAGE_KEY, SessionState, read_state
from smart_home_agent.agent.trace import AgentReply, TurnTrace
from smart_home_agent.config import Settings
from smart_home_agent.container import Services
from smart_home_agent.guardrail.callbacks import GuardrailReport, make_input_callback, make_output_callback
from smart_home_agent.guardrail.classifier import SemanticGuardrail
from smart_home_agent.guardrail.output_check import OutputValidator
from smart_home_agent.tools import build_tools

logger = logging.getLogger(__name__)

AGENT_NAME = "homepilot"
DEFAULT_USER = "customer"


# Verbatim instruction lines long enough that quoting them in an answer can only be a prompt leak.
_MIN_LEAK_LINE = 60


def _leak_markers(tools: list[Any]) -> list[str]:
    lines = [line.strip(" -") for line in BASE_INSTRUCTION.splitlines()]
    return [tool.__name__ for tool in tools] + [line for line in lines if len(line) >= _MIN_LEAK_LINE]


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
        model = Gemini(model=settings.agent.model, client_kwargs={"api_key": api_key} if api_key else None)
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
        generate_content_config=types.GenerateContentConfig(temperature=settings.agent.temperature),
        before_agent_callback=make_input_callback(input_guardrail) if input_guardrail else None,
        after_model_callback=make_output_callback(validator) if validator else None,
    )


class AgentService:
    """Runs conversation turns. Sessions live in memory for the lifetime of the process.

    All turns run on one long-lived event loop (in a background thread): ADK caches its Gemini
    client per loop, so a new loop per turn (`asyncio.run`) would leave clients bound to closed loops.
    """

    def __init__(self, agent: LlmAgent, app_name: str) -> None:
        self._app_name = app_name
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

    async def chat_async(
        self,
        session_id: str,
        text: str,
        user_id: str = DEFAULT_USER,
        on_tool_call: Callable[[str], None] | None = None,
    ) -> AgentReply:
        trace = TurnTrace()
        answer: list[str] = []
        language = detect_language(text)
        message = types.Content(role="user", parts=[types.Part(text=text)])
        events = self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
            state_delta={TURN_LANGUAGE_KEY: language, GUARDRAIL_KEY: None},
        )
        async for event in events:
            for call in event.get_function_calls():
                trace.add_call(call.id, call.name or "", dict(call.args or {}))
                if on_tool_call is not None:
                    on_tool_call(call.name or "")
            for response in event.get_function_responses():
                trace.add_response(response.id, response.name or "", response.response)
            if event.is_final_response() and event.content and event.content.parts:
                answer.extend(part.text for part in event.content.parts if part.text and not part.thought)
            if event.error_message:
                logger.warning("agent error event: %s", event.error_message)
        session = await self._sessions.get_session(app_name=self._app_name, user_id=user_id, session_id=session_id)
        state = session.state if session else {}
        report = state.get(GUARDRAIL_KEY)
        return AgentReply(
            text="".join(answer).strip(),
            detected_language=language,
            trace=trace,
            state=read_state(state),
            guardrail=GuardrailReport.model_validate(report) if report else None,
        )

    async def state_async(self, session_id: str, user_id: str = DEFAULT_USER) -> SessionState:
        session = await self._sessions.get_session(app_name=self._app_name, user_id=user_id, session_id=session_id)
        return read_state(session.state) if session else SessionState()
