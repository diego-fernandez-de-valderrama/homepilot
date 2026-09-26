"""Calls Gemini with a structured response schema and maps the answer to domain objects."""

from dataclasses import dataclass
from typing import Any, Protocol

from google.genai import types

from catalog_ingestion.domain.enrichment import LLMEnrichment, WebPage
from catalog_ingestion.domain.facts import CompatibilityFact, Requirement
from catalog_ingestion.domain.product import NormalizedProduct
from catalog_ingestion.llm.client import TextGenerator
from catalog_ingestion.llm.prompts import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    build_prompt,
)
from catalog_ingestion.schemas.llm_enrichment import LLMEnrichmentSchema
from catalog_ingestion.schemas.mappers import llm_from_schema


@dataclass(frozen=True, slots=True)
class LLMResult:
    enrichment: LLMEnrichment
    raw_output: dict[str, Any]  # validated LLMEnrichmentSchema dump, cached in PostgreSQL
    model: str
    prompt_version: str


def from_cached_output(raw_output: dict[str, Any], model: str, prompt_version: str) -> LLMResult:
    schema = LLMEnrichmentSchema.model_validate(raw_output)
    return LLMResult(llm_from_schema(schema), raw_output, model, prompt_version)


class Enricher(Protocol):
    @property
    def model(self) -> str: ...

    def enrich(
        self,
        product: NormalizedProduct,
        facts: tuple[CompatibilityFact, ...],
        requirements: tuple[Requirement, ...],
        web_page: WebPage | None,
    ) -> LLMResult: ...


class LLMEnricher:
    def __init__(self, client: TextGenerator, temperature: float = 0.0) -> None:
        self._client = client
        self._temperature = temperature

    @property
    def model(self) -> str:
        return self._client.model

    def enrich(
        self,
        product: NormalizedProduct,
        facts: tuple[CompatibilityFact, ...],
        requirements: tuple[Requirement, ...],
        web_page: WebPage | None,
    ) -> LLMResult:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=self._temperature,
            response_mime_type="application/json",
            response_schema=LLMEnrichmentSchema,
        )
        response = self._client.generate(build_prompt(product, facts, requirements, web_page), config)
        if not response.text:
            raise RuntimeError("Gemini returned an empty response")
        schema = LLMEnrichmentSchema.model_validate_json(response.text)
        return LLMResult(
            enrichment=llm_from_schema(schema),
            raw_output=schema.model_dump(mode="json"),
            model=self._client.model,
            prompt_version=PROMPT_VERSION,
        )
