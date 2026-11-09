"""LLM enrichment: one Gemini call per product with a structured response schema.

`PromptBuilder` renders the versioned prompt (catalog entry, web page text, deterministic facts, allowed
category keys; the system instruction is in private `_system_instruction`); bump `PromptBuilder.VERSION`
on any prompt change. `LLMEnricher` (the `Enricher` protocol) calls Gemini and returns an `LLMResult`,
whose `LLMEnrichment` is still untrusted until the validator accepts it. `LLMResult.from_cached` reads an
output stored by an earlier run.
"""

from catalog_ingestion.enrichment.llm.enricher import Enricher
from catalog_ingestion.enrichment.llm.llm_enricher import LLMEnricher
from catalog_ingestion.enrichment.llm.llm_result import LLMResult
from catalog_ingestion.enrichment.llm.prompt_builder import PromptBuilder

__all__ = ["Enricher", "LLMEnricher", "LLMResult", "PromptBuilder"]
