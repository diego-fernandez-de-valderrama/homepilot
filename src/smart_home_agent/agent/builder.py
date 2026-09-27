"""Builds the single HomePilot `LlmAgent`: chat model, tools, instruction provider and guardrail callbacks."""

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.genai import types

from smart_home_agent.agent.constants import AGENT_NAME
from smart_home_agent.agent.model import ResilientGemini, RetryPolicy
from smart_home_agent.agent.prompts import BASE_INSTRUCTION, MEMORY_INSTRUCTION, build_instruction
from smart_home_agent.config import Settings
from smart_home_agent.container import Services
from smart_home_agent.guardrail.callbacks import make_input_callback, make_output_callback
from smart_home_agent.guardrail.classifier import SemanticGuardrail
from smart_home_agent.guardrail.output_check import OutputValidator
from smart_home_agent.tools import build_tools
from smart_home_agent.tools.cart import make_cart_result_callback

# Verbatim instruction lines long enough that quoting them in an answer can only be a prompt leak.
_MIN_LEAK_LINE = 60


def build_agent(
    services: Services, settings: Settings, guardrail: SemanticGuardrail | None = None, model: Any = None
) -> LlmAgent:
    """Builds the agent without any network call (the Gemini client is created lazily).

    The guardrail wraps the unchanged agent through ADK callbacks: the semantic input check runs
    before the model (only when a `guardrail` is given and AGENT_GUARDRAIL_ENABLED is true) and the
    deterministic output check after it (AGENT_GUARDRAIL_OUTPUT_CHECK). Answer tags that would never render
    are always removed from the answer, for the interface and the history. `model` replaces the Gemini
    model (tests only).
    """
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
        model=model if model is not None else _build_model(settings),
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
        after_model_callback=make_output_callback(validator),
        after_tool_callback=make_cart_result_callback(services),
    )


def _build_model(settings: Settings) -> ResilientGemini:
    api_key = settings.gemini.api_key.get_secret_value() if settings.gemini.api_key else None
    options = settings.agent
    policy = RetryPolicy(options.model_retries, options.model_retry_initial_delay, options.model_retry_max_delay)
    return ResilientGemini(
        model=options.model,
        client_kwargs={"api_key": api_key} if api_key else None,
        retry_options=policy.http_options(),
        empty_retries=policy.retries,
        retry_initial_delay=policy.initial_delay,
        retry_max_delay=policy.max_delay,
    )


def _leak_markers(tools: list[FunctionTool]) -> list[str]:
    lines = [line.strip(" -") for line in (BASE_INSTRUCTION + MEMORY_INSTRUCTION).splitlines()]
    return [tool.name for tool in tools] + [line for line in lines if len(line) >= _MIN_LEAK_LINE]
