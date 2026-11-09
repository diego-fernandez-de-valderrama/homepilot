from dataclasses import dataclass
from typing import Any

from catalog_ingestion.models import LLMEnrichment, LLMEnrichmentMapper, LLMEnrichmentSchema


@dataclass(frozen=True, slots=True)
class LLMResult:
    enrichment: LLMEnrichment
    raw_output: dict[str, Any]  # validated LLMEnrichmentSchema dump, cached in PostgreSQL
    model: str
    prompt_version: str

    @classmethod
    def from_cached(cls, raw_output: dict[str, Any], model: str, prompt_version: str) -> "LLMResult":
        """A result stored by an earlier run (raises `ValidationError` when it no longer fits the schema)."""
        schema = LLMEnrichmentSchema.model_validate(raw_output)
        return cls(LLMEnrichmentMapper.from_schema(schema), raw_output, model, prompt_version)
