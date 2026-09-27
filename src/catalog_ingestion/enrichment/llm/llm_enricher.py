from google.genai import types

from catalog_ingestion.core import TextGenerator
from catalog_ingestion.enrichment.llm.llm_result import LLMResult
from catalog_ingestion.enrichment.llm.prompt_builder import PromptBuilder
from catalog_ingestion.models import (
    CompatibilityFact,
    LLMEnrichmentMapper,
    LLMEnrichmentSchema,
    NormalizedProduct,
    Requirement,
    WebPage,
)


class LLMEnricher:
    """Calls Gemini with a structured response schema and maps the answer to domain objects."""

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
            system_instruction=PromptBuilder.SYSTEM_INSTRUCTION,
            temperature=self._temperature,
            response_mime_type="application/json",
            response_schema=LLMEnrichmentSchema,
        )
        response = self._client.generate(PromptBuilder.build(product, facts, requirements, web_page), config)
        if not response.text:
            raise RuntimeError("Gemini returned an empty response")
        schema = LLMEnrichmentSchema.model_validate_json(response.text)
        return LLMResult(
            enrichment=LLMEnrichmentMapper.from_schema(schema),
            raw_output=schema.model_dump(mode="json"),
            model=self._client.model,
            prompt_version=PromptBuilder.VERSION,
        )
