from catalog_ingestion.enrichment.validation._source_texts import SourceTexts
from catalog_ingestion.models import Evidence
from catalog_ingestion.vocabulary import FactSource


class ClaimProvenance:
    """Evidence and confidence of an accepted LLM claim. Confidence is assigned by rule, never taken from
    the model."""

    CONFIDENCE_LLM_FROM_CATALOG = 0.9
    CONFIDENCE_LLM_FROM_WEB = 0.8
    # Page text read through Gemini url_context is itself model output, not a verbatim page copy.
    CONFIDENCE_LLM_FROM_GENERATED_WEB = 0.6
    CONFIDENCE_LLM_DERIVED = 0.6
    GENERATED_WEB_METHOD = "gemini_url_context"

    @staticmethod
    def confidence(source: FactSource, sources: SourceTexts) -> float:
        if source is not FactSource.WEB:
            return ClaimProvenance.CONFIDENCE_LLM_FROM_CATALOG
        if sources.web_method == ClaimProvenance.GENERATED_WEB_METHOD:
            return ClaimProvenance.CONFIDENCE_LLM_FROM_GENERATED_WEB
        return ClaimProvenance.CONFIDENCE_LLM_FROM_WEB

    @staticmethod
    def evidence(source: FactSource, quote: str, sources: SourceTexts) -> Evidence:
        if source is FactSource.WEB:
            generated = sources.web_method == ClaimProvenance.GENERATED_WEB_METHOD
            field = "web_page:url_context" if generated else "web_page"
            return Evidence(FactSource.WEB, quote, field=field, url=sources.web_url)
        return Evidence(FactSource.CATALOG, quote, field="catalog_text")
