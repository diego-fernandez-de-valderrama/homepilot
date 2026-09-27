from catalog_ingestion.core import TextNormalizer
from catalog_ingestion.enrichment.validation._claim_provenance import ClaimProvenance
from catalog_ingestion.enrichment.validation._compatibility_claim_check import CompatibilityClaimCheck
from catalog_ingestion.enrichment.validation._fact_merger import FactMerger
from catalog_ingestion.enrichment.validation._requirement_claim_check import RequirementClaimCheck
from catalog_ingestion.enrichment.validation._source_texts import SourceTexts
from catalog_ingestion.enrichment.validation._spec_check import SpecCheck
from catalog_ingestion.models import (
    CompatibilityFact,
    CompletenessReport,
    EnrichedProduct,
    FieldProvenance,
    LLMEnrichment,
    NormalizedProduct,
    Requirement,
    Spec,
    WebPage,
)
from catalog_ingestion.vocabulary import CategoryVocabulary, FactSource, Method, WebStatus


class Validator:
    """Combines deterministic facts and (optional) LLM output into a validated `EnrichedProduct`."""

    MAX_KEY_FEATURES = 8
    MAX_USE_CASES = 6

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
                outcome = CompatibilityClaimCheck.check(claim, sources)
                if outcome.note:
                    notes.append(outcome.note)
                if outcome.value is not None:
                    llm_facts.append(outcome.value)
            for claim in llm.requirement_claims:
                requirement_outcome = RequirementClaimCheck.check(claim, sources)
                if requirement_outcome.note:
                    notes.append(requirement_outcome.note)
                if requirement_outcome.value is not None:
                    llm_requirements.append(requirement_outcome.value)
        merged_facts, conflict_notes = FactMerger.merge_facts(facts, llm_facts)
        notes.extend(conflict_notes)
        merged_requirements = FactMerger.merge_requirements(requirements, llm_requirements)

        # Category: the URL slug is authoritative; the LLM only fills brand-page slugs.
        category = product.category
        if category is not None:
            provenance.append(
                FieldProvenance("category", FactSource.CATALOG, Method.DETERMINISTIC, 1.0, "url category slug")
            )
        elif llm is not None and llm.category in CategoryVocabulary.KEYS:
            category = llm.category
            provenance.append(
                FieldProvenance("category", FactSource.LLM, Method.LLM, ClaimProvenance.CONFIDENCE_LLM_DERIVED)
            )

        # Brand: known brand prefix of the title, else the LLM's brand if it appears in the title.
        brand = product.brand
        if brand is not None:
            provenance.append(FieldProvenance("brand", FactSource.CATALOG, Method.DETERMINISTIC, 1.0, "title prefix"))
        elif llm is not None and llm.brand:
            if TextNormalizer.normalize(llm.brand) in TextNormalizer.normalize(product.title):
                brand = llm.brand.strip()
                provenance.append(
                    FieldProvenance(
                        "brand", FactSource.CATALOG, Method.LLM, ClaimProvenance.CONFIDENCE_LLM_FROM_CATALOG, "title"
                    )
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
                if SpecCheck.supported(spec, sources):
                    kept_specs.append(spec)
                else:
                    notes.append(f"dropped spec '{spec.name}: {spec.value}': value not found in sources")
            specs = tuple(kept_specs)
            product_type = self._optional_text(llm.product_type)
            summary_en = self._optional_text(llm.summary_en)
            summary_de = self._optional_text(llm.summary_de)
            key_features = self._clean_list(llm.key_features, self.MAX_KEY_FEATURES)
            use_cases = self._clean_list(llm.use_cases, self.MAX_USE_CASES)
            for field in ("product_type", "summary_en", "summary_de", "key_features", "use_cases"):
                provenance.append(
                    FieldProvenance(
                        field,
                        FactSource.LLM,
                        Method.LLM,
                        ClaimProvenance.CONFIDENCE_LLM_DERIVED,
                        "derived from sources",
                    )
                )
            if specs:
                provenance.append(
                    FieldProvenance(
                        "specs",
                        FactSource.LLM,
                        Method.LLM,
                        ClaimProvenance.CONFIDENCE_LLM_FROM_CATALOG,
                        "values verified in sources",
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

    @staticmethod
    def _clean_list(values: tuple[str, ...], limit: int) -> tuple[str, ...]:
        cleaned = (value.strip() for value in values)
        return tuple(dict.fromkeys(value for value in cleaned if value))[:limit]

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None
