"""Input guardrail: classifies the user message by embedding similarity to semantic prototypes.

guardrail = SemanticGuardrail.create(gemini_embed(client), thresholds)   # embeds PROTOTYPES once
decision = guardrail.classify("Wie schließe ich den Neutralleiter an?")  # -> GuardrailDecision
"""

from smart_home_agent.guardrail.input._decision_rule import decide
from smart_home_agent.guardrail.input.category import BLOCKING, Category
from smart_home_agent.guardrail.input.decision import GuardrailDecision
from smart_home_agent.guardrail.input.embedding import TASK_TYPE, EmbedFn, gemini_embed
from smart_home_agent.guardrail.input.prototypes import PROTOTYPES
from smart_home_agent.guardrail.input.semantic_guardrail import SemanticGuardrail
from smart_home_agent.guardrail.input.thresholds import GuardrailThresholds

__all__ = [
    "BLOCKING",
    "PROTOTYPES",
    "TASK_TYPE",
    "Category",
    "EmbedFn",
    "GuardrailDecision",
    "GuardrailThresholds",
    "SemanticGuardrail",
    "decide",
    "gemini_embed",
]
