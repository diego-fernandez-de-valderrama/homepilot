"""Combines deterministic facts and (optional) LLM output into a validated EnrichedProduct."""

import re

from catalog_ingestion.domain.enrichment import (
    EnrichedProduct,
    FieldProvenance,
    LLMEnrichment,
    Spec,
    WebPage,
)
from catalog_ingestion.domain.enums import FactSource, Method, WebStatus
from catalog_ingestion.domain.facts import CompatibilityFact, Requirement
from catalog_ingestion.domain.product import NormalizedProduct
from catalog_ingestion.domain.quality import CompletenessReport
from catalog_ingestion.validation.evidence import SourceTexts, normalize_text
from catalog_ingestion.validation.merge import (
    CONFIDENCE_LLM_DERIVED,
    CONFIDENCE_LLM_FROM_CATALOG,
    compatibility_from_claim,
    merge_facts,
    merge_requirements,
    requirement_from_claim,
)
from catalog_ingestion.vocabulary.categories import CATEGORY_KEYS

MAX_KEY_FEATURES = 8
MAX_USE_CASES = 6
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _clean_list(values: tuple[str, ...], limit: int) -> tuple[str, ...]:
    cleaned = (value.strip() for value in values)
    return tuple(dict.fromkeys(value for value in cleaned if value))[:limit]


def _spec_supported(spec: Spec, sources: SourceTexts) -> bool:
    """A spec is kept when its value (or all of its numbers) appear in a source."""
    combined = f"{sources.catalog}\n{sources.web}"
    value = normalize_text(spec.value)
    if value and value in combined:
        return True
    numbers = _NUMBER.findall(spec.value)
    return bool(numbers) and all(number in combined for number in numbers)


def _optional_text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


class Validator:
    def validate(
        self,
        product: NormalizedProduct,
        completeness: CompletenessReport,
        facts: tuple[CompatibilityFact, ...],
        requirements: tuple[Requirement, ...],
        web_status: WebStatus,
        web_page: WebPage | None,
        llm: LLMEnrichment | None,
        enrichment_model: str | None,
        prompt_version: str | None,
    ) -> EnrichedProduct:
        sources = SourceTexts.build(product, web_page)
        notes: list[str] = []
        provenance: list[FieldProvenance] = []

        llm_facts: list[CompatibilityFact] = []
        llm_requirements: list[Requirement] = []
        if llm is not None:
            for claim in llm.compatibility_claims:
                outcome = compatibility_from_claim(claim, sources)
                if outcome.note:
                    notes.append(outcome.note)
                if outcome.value is not None:
                    llm_facts.append(outcome.value)
            for claim in llm.requirement_claims:
                outcome = requirement_from_claim(claim, sources)
                if outcome.note:
                    notes.append(outcome.note)
                if outcome.value is not None:
                    llm_requirements.append(outcome.value)
        merged_facts, conflict_notes = merge_facts(facts, llm_facts)
        notes.extend(conflict_notes)
        merged_requirements = merge_requirements(requirements, llm_requirements)

        # Category: the URL slug is authoritative; the LLM only fills brand-page slugs.
        category = product.category
        if category is not None:
            provenance.append(
                FieldProvenance("category", FactSource.CATALOG, Method.DETERMINISTIC, 1.0, "url category slug")
            )
        elif llm is not None and llm.category in CATEGORY_KEYS:
            category = llm.category
            provenance.append(FieldProvenance("category", FactSource.LLM, Method.LLM, CONFIDENCE_LLM_DERIVED))

        # Brand: known brand prefix of the title, else the LLM's brand if it appears in the title.
        brand = product.brand
        if brand is not None:
            provenance.append(FieldProvenance("brand", FactSource.CATALOG, Method.DETERMINISTIC, 1.0, "title prefix"))
        elif llm is not None and llm.brand:
            if normalize_text(llm.brand) in normalize_text(product.title):
                brand = llm.brand.strip()
                provenance.append(
                    FieldProvenance("brand", FactSource.CATALOG, Method.LLM, CONFIDENCE_LLM_FROM_CATALOG, "title")
                )
            else:
                notes.append(f"dropped brand '{llm.brand}': not found in title")

        specs: tuple[Spec, ...] = ()
        product_type = summary_en = summary_de = None
        key_features: tuple[str, ...] = ()
        use_cases: tuple[str, ...] = ()
        if llm is not None:
            kept_specs = []
            for spec in llm.specs:
                if _spec_supported(spec, sources):
                    kept_specs.append(spec)
                else:
                    notes.append(f"dropped spec '{spec.name}: {spec.value}': value not found in sources")
            specs = tuple(kept_specs)
            product_type = _optional_text(llm.product_type)
            summary_en = _optional_text(llm.summary_en)
            summary_de = _optional_text(llm.summary_de)
            key_features = _clean_list(llm.key_features, MAX_KEY_FEATURES)
            use_cases = _clean_list(llm.use_cases, MAX_USE_CASES)
            for field in ("product_type", "summary_en", "summary_de", "key_features", "use_cases"):
                provenance.append(
                    FieldProvenance(field, FactSource.LLM, Method.LLM, CONFIDENCE_LLM_DERIVED, "derived from sources")
                )
            if specs:
                provenance.append(
                    FieldProvenance(
                        "specs", FactSource.LLM, Method.LLM, CONFIDENCE_LLM_FROM_CATALOG, "values verified in sources"
                    )
                )

        if product.price.value is None or product.price.value <= 0:
            notes.append(f"invalid price '{product.price.raw.strip()}'")

        return EnrichedProduct(
            product=product,
            completeness=completeness,
            category=category,
            product_type=product_type,
            brand=brand,
            summary_en=summary_en,
            summary_de=summary_de,
            key_features=key_features,
            use_cases=use_cases,
            specs=specs,
            compatibility=merged_facts,
            requirements=merged_requirements,
            provenance=tuple(provenance),
            web_status=web_status,
            web_url=web_page.url if web_page is not None else None,
            web_method=web_page.method if web_page is not None and web_page.ok else None,
            enrichment_model=enrichment_model if llm is not None else None,
            prompt_version=prompt_version if llm is not None else None,
            validation_notes=tuple(notes),
        )
