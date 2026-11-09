from catalog_ingestion.core import Hashing
from catalog_ingestion.enrichment.llm import PromptBuilder
from catalog_ingestion.models import NormalizedProductMapper, WebPage
from catalog_ingestion.preparation import PreparedProduct


class EnrichmentKey:
    """Cache keys of the LLM output: an unchanged key means the stored output is reused."""

    @staticmethod
    def current(prepared: PreparedProduct, web_page: WebPage | None, prompt_version: str) -> str:
        """The exact input the LLM sees.

        It covers the full prompt (product, web text, deterministic facts and requirements, allowed
        category keys) and the system instruction, so vocabulary or extraction changes that alter what
        the model is shown also invalidate the cache.

        The model and the API key are deliberately not part of it: switching either does not redo
        products that are already enriched (use `--force` for that). The model that produced each
        output is still stored with it for provenance.
        """
        return Hashing.sha256_json(
            {
                "system": PromptBuilder.SYSTEM_INSTRUCTION,
                "prompt": PromptBuilder.build(prepared.product, prepared.facts, prepared.requirements, web_page),
                "prompt_version": prompt_version,
            }
        )

    @staticmethod
    def previous(prepared: PreparedProduct, web_page: WebPage | None, prompt_version: str) -> str:
        """Key format used before the full prompt was hashed (product + web text only); still accepted so
        existing results are reused (and re-stored under the current key) instead of being recomputed."""
        return Hashing.sha256_json(
            {
                "product": NormalizedProductMapper.to_schema(prepared.product).model_dump(mode="json"),
                "web": web_page.text if web_page is not None and web_page.ok else None,
                "prompt_version": prompt_version,
            }
        )

    @staticmethod
    def legacy(prepared: PreparedProduct, web_page: WebPage | None, model: str, prompt_version: str) -> str:
        """Oldest key format, which also contained the model; still accepted like `previous`."""
        return Hashing.sha256_json(
            {
                "product": NormalizedProductMapper.to_schema(prepared.product).model_dump(mode="json"),
                "web": web_page.text if web_page is not None and web_page.ok else None,
                "model": model,
                "prompt_version": prompt_version,
            }
        )
