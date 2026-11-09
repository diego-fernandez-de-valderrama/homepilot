from typing import Protocol

from catalog_ingestion.enrichment.llm.llm_result import LLMResult
from catalog_ingestion.models import CompatibilityFact, NormalizedProduct, Requirement, WebPage


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
