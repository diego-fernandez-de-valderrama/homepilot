"""Semantic input guardrail and deterministic output checks around the existing HomePilot agent (no second agent).

    guardrail = SemanticGuardrail.create(gemini_embed(client), thresholds)       # startup: embeds the prototypes
    validator = OutputValidator(catalog, guardrail, leak_markers)
    LlmAgent(..., before_agent_callback=InputGuardrailCallback(guardrail),
             after_model_callback=OutputGuardrailCallback(validator))

Flow of one turn:
1. `input/`: the user message is embedded and compared (cosine, locally) with cached prototype embeddings per
   `Category`. ELECTRICAL and PROMPT_INJECTION (OFF_TOPIC only when enabled) are blocked.
2. `replies/`: a blocked message gets a deterministic reply (`ResponseType`) without any model call.
3. `output/`: the final model answer is checked against the catalog (electrical instructions, unknown products,
   unsupported compatibility claims, prompt leaks, off-topic drift); a failed check swaps in a fallback reply.
4. `callbacks/`: the ADK callbacks that run steps 1-3 and record a `GuardrailReport` in the session state.
"""

from smart_home_agent.guardrail.callbacks import InputGuardrailCallback, OutputGuardrailCallback
from smart_home_agent.guardrail.input import (
    Category,
    GuardrailDecision,
    GuardrailThresholds,
    SemanticGuardrail,
    gemini_embed,
)
from smart_home_agent.guardrail.output import OutputValidator, Violation
from smart_home_agent.guardrail.replies import ResponseType
from smart_home_agent.guardrail.report import GuardrailReport

__all__ = [
    "Category",
    "GuardrailDecision",
    "GuardrailReport",
    "GuardrailThresholds",
    "InputGuardrailCallback",
    "OutputGuardrailCallback",
    "OutputValidator",
    "ResponseType",
    "SemanticGuardrail",
    "Violation",
    "gemini_embed",
]
