"""ADK callbacks that put the guardrail around the existing agent (no second agent).

- `InputGuardrailCallback` (`before_agent_callback`): classifies the user message before the first model call and
  answers a blocked one with a deterministic reply.
- `OutputGuardrailCallback` (`after_model_callback`): removes answer tags that would never render and replaces an
  answer that fails a critical check with a fallback.

Deterministic replies use role "model" and are authored by the agent itself, so ADK keeps them in
the history as the model's own previous turns (not as "[agent] said" context). The next model call
sees exactly what the user saw, and a rejected answer never enters the history.
"""

from smart_home_agent.guardrail.callbacks.input_callback import InputGuardrailCallback
from smart_home_agent.guardrail.callbacks.output_callback import OutputGuardrailCallback

__all__ = ["InputGuardrailCallback", "OutputGuardrailCallback"]
