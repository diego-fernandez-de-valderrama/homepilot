import json

import pytest
from google.genai import types
from pydantic import ValidationError

from catalog_ingestion.domain.enums import Dimension, FactSource
from catalog_ingestion.extraction.compatibility import extract_compatibility
from catalog_ingestion.extraction.requirements import extract_requirements
from catalog_ingestion.llm.enricher import LLMEnricher, from_cached_output
from catalog_ingestion.llm.prompts import build_prompt
from tests.conftest import BOSCH_CONTROLLER, SPARSE_MATTER, load_normalized

ANSWER = {
    "category": "contact_sensor",
    "product_type": "Door/window contact sensor",
    "brand": "Bosch",
    "summary_en": "Battery-powered window contact.",
    "summary_de": "Batteriebetriebener Fensterkontakt.",
    "key_features": ["Matter support"],
    "use_cases": ["Window monitoring"],
    "specs": [{"name": "Dimensions", "value": "23 x 22 x 75 mm", "unit": "mm"}],
    "compatibility_claims": [
        {"dimension": "ecosystem", "value": "Matter", "status": "supported", "source": "catalog",
         "evidence_quote": "[+M] Matter"}
    ],
    "requirements": [],
}  # fmt: skip


class FakeClient:
    model = "fake-model"

    def __init__(self, text: str) -> None:
        self._text = text
        self.prompts: list[str] = []

    def generate(self, contents: str, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        self.prompts.append(contents)
        content = types.Content(role="model", parts=[types.Part(text=self._text)])
        return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def _enrich(text: str):
    product = load_normalized(SPARSE_MATTER)
    client = FakeClient(text)
    result = LLMEnricher(client).enrich(product, extract_compatibility(product), (), None)
    return result, client


def test_enricher_parses_structured_output():
    result, _ = _enrich(json.dumps(ANSWER))
    assert result.enrichment.category == "contact_sensor"
    claim = result.enrichment.compatibility_claims[0]
    assert claim.dimension is Dimension.ECOSYSTEM and claim.source is FactSource.CATALOG
    assert result.model == "fake-model"
    restored = from_cached_output(result.raw_output, result.model, result.prompt_version)
    assert restored.enrichment == result.enrichment


def test_enricher_rejects_invalid_output():
    with pytest.raises(ValidationError):
        _enrich(json.dumps({**ANSWER, "category": "toaster"}))


def test_prompt_contains_sources_in_quotable_form():
    product = load_normalized(BOSCH_CONTROLLER)
    prompt = build_prompt(product, extract_compatibility(product), extract_requirements(product), None)
    assert "## SOURCE: catalog" in prompt
    assert "Unterstützte Sprachsteuerung: Google Assistant, Amazon Alexa, Apple Siri" in prompt
    assert "## SOURCE: web\n(not available)" in prompt
    assert "- voice_assistant: Apple Siri (supported)" in prompt
