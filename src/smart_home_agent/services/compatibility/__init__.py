"""Deterministic compatibility decisions from the structured facts in PostgreSQL.

    CompatibilityEvaluator.evaluate(product, terms, owned_devices)   # pure, one product -> CompatibilityResult
    CompatibilityService(catalog, accessories).check(ids, terms)     # reads the catalog, adds hub accessories

Rules:
  * a `supported` fact for the canonical value (and no `unsupported` one) -> supported;
  * only `unsupported` facts -> unsupported;
  * contradicting facts -> unknown (with a note);
  * no fact at all -> unknown. Missing information is never turned into supported or unsupported.
Related concepts (Siri vs HomeKit, Google Assistant vs Google Home) only produce notes.
"""

from smart_home_agent.services.compatibility.compatibility_evaluator import CompatibilityEvaluator
from smart_home_agent.services.compatibility.compatibility_service import CompatibilityService

__all__ = ["CompatibilityEvaluator", "CompatibilityService"]
