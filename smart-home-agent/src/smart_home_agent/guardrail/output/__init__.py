"""Output guardrail: deterministic checks of the final answer (no second model).

    validator = OutputValidator(catalog, guardrail, leak_markers)
    violations = validator.validate(answer, tool_responses, session_product_ids)   # -> list[Violation]

One private module per check (`_electrical_check`, `_prompt_leak_check`, `_unknown_product_check`,
`_compatibility_check`, `_off_topic_check`); `OutputValidator` runs them in that order.
"""

from smart_home_agent.guardrail.output.output_validator import OutputValidator
from smart_home_agent.guardrail.output.product_lookup import ProductLookup
from smart_home_agent.guardrail.output.violation import Violation, ViolationKind

__all__ = ["OutputValidator", "ProductLookup", "Violation", "ViolationKind"]
