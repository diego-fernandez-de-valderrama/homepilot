"""Deterministic checks of the final answer (no second model).

Every check is conservative: it only flags what it can show to be wrong, because a failed check
replaces the whole answer with a fallback. Unknown stays unknown: a claim that cannot be linked to a
product, or a term that cannot be resolved, passes.

- electrical: practical wiring / mains installation steps (EN/DE patterns, refusals excluded);
- unknown_product: a product id (in prose or in an answer tag) that is neither in this turn's tool results
  nor in the catalog;
- unsupported_compatibility: a positive "works with X" claim about a product whose catalog facts do
  not support X (PostgreSQL facts, never the model's wording or Qdrant);
- prompt_leak: internal tool names or verbatim lines of the system instruction;
- off_topic: only for answers produced without any tool, one embedding call against the prototypes.
"""

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from smart_home_agent.guardrail.input import SemanticGuardrail
from smart_home_agent.guardrail.output._compatibility_check import CompatibilityCheck
from smart_home_agent.guardrail.output._electrical_check import ElectricalCheck
from smart_home_agent.guardrail.output._off_topic_check import OffTopicCheck
from smart_home_agent.guardrail.output._prompt_leak_check import PromptLeakCheck
from smart_home_agent.guardrail.output._sentences import split_sentences
from smart_home_agent.guardrail.output._tool_products import tool_products
from smart_home_agent.guardrail.output._unknown_product_check import UnknownProductCheck
from smart_home_agent.guardrail.output.product_lookup import ProductLookup
from smart_home_agent.guardrail.output.violation import Violation

logger = logging.getLogger(__name__)


class OutputValidator:
    def __init__(
        self,
        catalog: ProductLookup,
        guardrail: SemanticGuardrail | None = None,
        leak_markers: Sequence[str] = (),
        min_domain_check_chars: int = 200,
    ) -> None:
        self._electrical = ElectricalCheck()
        self._prompt_leak = PromptLeakCheck(leak_markers)
        self._unknown_products = UnknownProductCheck(catalog)
        self._compatibility = CompatibilityCheck(catalog)
        self._off_topic = OffTopicCheck(guardrail, min_domain_check_chars)

    def validate(
        self,
        text: str,
        tool_responses: Sequence[Mapping[str, Any]] = (),
        session_product_ids: Sequence[str] = (),
    ) -> list[Violation]:
        """`session_product_ids`: products discussed earlier (session state), so a claim in a turn without
        tool calls ("does the first one work with Alexa?" -> "yes, it does") is still checked."""
        sentences = split_sentences(text)
        violations = [
            *self._electrical.check(sentences),
            *self._prompt_leak.check(text),
        ]
        products = tool_products(tool_responses)
        try:
            violations += self._unknown_products.check(text, products)
            violations += self._compatibility.check(sentences, products, session_product_ids)
        except Exception:  # the catalog being down must not turn every answer into a fallback
            logger.warning("output check: catalog lookup failed, product checks skipped", exc_info=True)
        if not violations and not tool_responses:
            violations += self._off_topic.check(text)
        return violations
