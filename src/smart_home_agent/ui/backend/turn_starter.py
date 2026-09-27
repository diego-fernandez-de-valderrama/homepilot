from collections.abc import Callable
from concurrent.futures import Future

from smart_home_agent.agent import AgentReply

# Submits a turn to the agent service; called with the `on_tool_call` listener as keyword argument.
type TurnStarter = Callable[..., Future[AgentReply]]
