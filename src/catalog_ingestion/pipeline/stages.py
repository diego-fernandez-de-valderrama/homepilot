"""Per-product stage functions. Deterministic stages are pure; I/O happens in the orchestrator."""

from dataclasses import dataclass

from catalog_ingestion.core.hashing import sha256_json
from catalog_ingestion.domain.enrichment import WebPage
from catalog_ingestion.domain.facts import CompatibilityFact, Requirement
from catalog_ingestion.domain.product import NormalizedProduct, RawProduct
from catalog_ingestion.domain.quality import CompletenessReport
from catalog_ingestion.extraction.compatibility import extract_compatibility
from catalog_ingestion.extraction.requirements import extract_requirements
from catalog_ingestion.llm.prompts import SYSTEM_INSTRUCTION, build_prompt
from catalog_ingestion.normalization.normalizer import normalize
from catalog_ingestion.quality.completeness import assess_completeness
from catalog_ingestion.schemas.mappers import normalized_to_schema


@dataclass(frozen=True, slots=True)
class PreparedProduct:
    raw: RawProduct
    raw_hash: str
    product: NormalizedProduct
    facts: tuple[CompatibilityFact, ...]
    requirements: tuple[Requirement, ...]
    completeness: CompletenessReport


def prepare(raw: RawProduct) -> PreparedProduct:
    """Normalization, deterministic extraction and completeness analysis."""
    product = normalize(raw)
    facts = extract_compatibility(product)
    return PreparedProduct(
        raw=raw,
        raw_hash=sha256_json(dict(raw.original)),
        product=product,
        facts=facts,
        requirements=extract_requirements(product),
        completeness=assess_completeness(product, facts),
    )


def enrichment_hash(prepared: PreparedProduct, web_page: WebPage | None, prompt_version: str) -> str:
    """The exact input the LLM sees. Unchanged hash -> the stored output is reused.

    It covers the full prompt (product, web text, deterministic facts and requirements, allowed
    category keys) and the system instruction, so vocabulary or extraction changes that alter what
    the model is shown also invalidate the cache.

    The model and the API key are deliberately not part of it: switching either does not redo
    products that are already enriched (use `--force` for that). The model that produced each
    output is still stored with it for provenance.
    """
    return sha256_json(
        {
            "system": SYSTEM_INSTRUCTION,
            "prompt": build_prompt(prepared.product, prepared.facts, prepared.requirements, web_page),
            "prompt_version": prompt_version,
        }
    )


def previous_enrichment_hash(prepared: PreparedProduct, web_page: WebPage | None, prompt_version: str) -> str:
    """Cache key format used before the full prompt was hashed (product + web text only); still
    accepted so existing results are reused (and re-stored under the new key) instead of being recomputed."""
    return sha256_json(
        {
            "product": normalized_to_schema(prepared.product).model_dump(mode="json"),
            "web": web_page.text if web_page is not None and web_page.ok else None,
            "prompt_version": prompt_version,
        }
    )


def legacy_enrichment_hash(prepared: PreparedProduct, web_page: WebPage | None, model: str, prompt_version: str) -> str:
    """Oldest cache key format, which also contained the model; still accepted like `previous_enrichment_hash`."""
    return sha256_json(
        {
            "product": normalized_to_schema(prepared.product).model_dump(mode="json"),
            "web": web_page.text if web_page is not None and web_page.ok else None,
            "model": model,
            "prompt_version": prompt_version,
        }
    )
