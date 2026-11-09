"""ADK agent layer: one `LlmAgent` (`build_agent`) and its synchronous facade (`AgentService`).

    agent = build_agent(services, settings, guardrail)
    service = AgentService(agent, app_name, rich_content, cart, profiles)
    reply = service.chat(session_id, "Ich suche ein Thermostat")   # -> AgentReply

google-adk 2.x flags two features this agent relies on as EXPERIMENTAL and prints a UserWarning once per
process for each: the JSON-schema tool declarations (enabled by default) and tool confirmation (the cart
tools). Both are verified by tests (tests/unit/test_tools.py, tests/unit/test_cart_agent.py), so only those
exact warnings are silenced; all other warnings stay.
"""

import warnings

warnings.filterwarnings(
    "ignore",
    message=r"\[EXPERIMENTAL\] feature FeatureName\.(JSON_SCHEMA_FOR_FUNC_DECL|TOOL_CONFIRMATION) is enabled",
    category=UserWarning,
)

from smart_home_agent.agent.builder import build_agent  # noqa: E402 (after the warning filter)
from smart_home_agent.agent.constants import DEFAULT_USER  # noqa: E402
from smart_home_agent.agent.reply import AgentReply, ToolCallTrace, TurnTrace  # noqa: E402
from smart_home_agent.agent.service import AgentService  # noqa: E402

__all__ = ["DEFAULT_USER", "AgentReply", "AgentService", "ToolCallTrace", "TurnTrace", "build_agent"]
