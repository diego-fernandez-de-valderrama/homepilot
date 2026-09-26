"""Conversions between boundary schemas (pydantic) and domain models (frozen dataclasses).

This is the only module that knows both representations.
"""

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from catalog_ingestion.domain.enrichment import (
    CompatibilityClaim,
    EnrichedProduct,
    FieldProvenance,
    LLMEnrichment,
    RequirementClaim,
    Spec,
)
from catalog_ingestion.domain.enums import (
    Dimension,
    FactSource,
    FactStatus,
    Necessity,
    RequirementKind,
)
from catalog_ingestion.domain.facts import CompatibilityFact, Evidence, Requirement
from catalog_ingestion.domain.product import (
    AttributeEntry,
    Description,
    NormalizedProduct,
    ParsedAttributes,
    Price,
    RawProduct,
    SubtitleParts,
)
from catalog_ingestion.domain.quality import CompletenessReport
from catalog_ingestion.schemas.catalog_product import (
    AttributeSchema,
    CatalogProductSchema,
    CompatibilityFactSchema,
    CompletenessSchema,
    EvidenceSchema,
    FieldProvenanceSchema,
    KeyValueSchema,
    NormalizedProductSchema,
    PriceSchema,
    RequirementSchema,
    SpecOutSchema,
    WebInfoSchema,
)
from catalog_ingestion.schemas.llm_enrichment import LLMEnrichmentSchema
from catalog_ingestion.schemas.qdrant_payload import QdrantPayloadSchema
from catalog_ingestion.schemas.raw_product import RawProductSchema
from catalog_ingestion.vocabulary.categories import category_by_key
from catalog_ingestion.vocabulary.compatibility import label_for

# --- raw input ---------------------------------------------------------------------------


def raw_from_schema(schema: RawProductSchema, original: Mapping[str, Any]) -> RawProduct:
    return RawProduct(
        id=schema.id,
        title=schema.title,
        subtitle=schema.subtitle,
        price=schema.price,
        variants=tuple(schema.variants),
        description=schema.description,
        attributes=schema.attributes,
        image=schema.image,
        url=schema.url,
        original=MappingProxyType(dict(original)),
    )


# --- LLM output --------------------------------------------------------------------------


def llm_from_schema(schema: LLMEnrichmentSchema) -> LLMEnrichment:
    return LLMEnrichment(
        category=schema.category.value if schema.category else None,
        product_type=schema.product_type,
        brand=schema.brand,
        summary_en=schema.summary_en,
        summary_de=schema.summary_de,
        key_features=tuple(schema.key_features),
        use_cases=tuple(schema.use_cases),
        specs=tuple(Spec(spec.name, spec.value, spec.unit) for spec in schema.specs),
        compatibility_claims=tuple(
            CompatibilityClaim(
                dimension=Dimension(claim.dimension),
                value=claim.value,
                status=FactStatus(claim.status),
                source=FactSource(claim.source),
                evidence_quote=claim.evidence_quote,
            )
            for claim in schema.compatibility_claims
        ),
        requirement_claims=tuple(
            RequirementClaim(
                item=claim.item,
                kind=claim.kind,
                necessity=claim.necessity,
                alternatives=tuple(claim.alternatives),
                source=FactSource(claim.source),
                evidence_quote=claim.evidence_quote,
            )
            for claim in schema.requirements
        ),
    )


# --- catalog product (PostgreSQL JSONB / phase-2 API) --------------------------------------


def _float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)).quantize(Decimal("0.01")) if value is not None else None


def price_to_schema(price: Price) -> PriceSchema:
    return PriceSchema(
        value=_float(price.value),
        currency=price.currency,
        original_value=_float(price.original_value),
        savings=_float(price.savings),
        raw=price.raw,
    )


def normalized_to_schema(product: NormalizedProduct) -> NormalizedProductSchema:
    return NormalizedProductSchema(
        id=product.id,
        title=product.title,
        subtitle=product.subtitle,
        subtitle_features=list(product.subtitle_parts.features),
        subtitle_properties=[KeyValueSchema(key=k, value=v) for k, v in product.subtitle_parts.properties],
        brand=product.brand,
        category_slug=product.category_slug,
        category=product.category,
        price=price_to_schema(product.price),
        variants=list(product.variants),
        description_highlights=list(product.description.highlights),
        description_text=product.description.text,
        badges=list(product.attributes.badges),
        attributes=[AttributeSchema(section=e.section, key=e.key, value=e.value) for e in product.attributes.entries],
        unparsed_attribute_lines=list(product.attributes.unparsed_lines),
        ean=product.ean,
        is_smart_home=product.is_smart_home,
        image_url=product.image_url,
        source_url=product.source_url,
    )


def normalized_from_schema(schema: NormalizedProductSchema) -> NormalizedProduct:
    return NormalizedProduct(
        id=schema.id,
        title=schema.title,
        subtitle=schema.subtitle,
        subtitle_parts=SubtitleParts(
            features=tuple(schema.subtitle_features),
            properties=tuple((kv.key, kv.value) for kv in schema.subtitle_properties),
        ),
        brand=schema.brand,
        category_slug=schema.category_slug,
        category=schema.category,
        price=Price(
            value=_decimal(schema.price.value),
            currency=schema.price.currency,
            original_value=_decimal(schema.price.original_value),
            savings=_decimal(schema.price.savings),
            raw=schema.price.raw,
        ),
        variants=tuple(schema.variants),
        description=Description(highlights=tuple(schema.description_highlights), text=schema.description_text),
        attributes=ParsedAttributes(
            badges=tuple(schema.badges),
            entries=tuple(AttributeEntry(a.section, a.key, a.value) for a in schema.attributes),
            unparsed_lines=tuple(schema.unparsed_attribute_lines),
        ),
        ean=schema.ean,
        is_smart_home=schema.is_smart_home,
        image_url=schema.image_url,
        source_url=schema.source_url,
    )


def _evidence_to_schema(evidence: Evidence) -> EvidenceSchema:
    return EvidenceSchema(source=evidence.source, text=evidence.text, field=evidence.field, url=evidence.url)


def _evidence_from_schema(schema: EvidenceSchema) -> Evidence:
    return Evidence(source=schema.source, text=schema.text, field=schema.field, url=schema.url)


def fact_to_schema(fact: CompatibilityFact) -> CompatibilityFactSchema:
    return CompatibilityFactSchema(
        dimension=fact.dimension,
        raw_value=fact.raw_value,
        canonical_value=fact.canonical_value,
        label=label_for(fact.canonical_value),
        status=fact.status,
        evidence=_evidence_to_schema(fact.evidence),
        confidence=fact.confidence,
        method=fact.method,
    )


def requirement_to_schema(requirement: Requirement) -> RequirementSchema:
    return RequirementSchema(
        item=requirement.item,
        canonical_item=requirement.canonical_item,
        kind=requirement.kind,
        necessity=requirement.necessity,
        alternatives=list(requirement.alternatives),
        evidence=_evidence_to_schema(requirement.evidence),
        confidence=requirement.confidence,
        method=requirement.method,
    )


def enriched_to_catalog(enriched: EnrichedProduct) -> CatalogProductSchema:
    product = enriched.product
    category = category_by_key(enriched.category)
    report = enriched.completeness
    return CatalogProductSchema(
        id=product.id,
        title=product.title,
        brand=enriched.brand,
        category=enriched.category,
        category_label_en=category.label_en if category else None,
        category_label_de=category.label_de if category else None,
        product_type=enriched.product_type,
        is_smart_home=product.is_smart_home,
        price=price_to_schema(product.price),
        summary_en=enriched.summary_en,
        summary_de=enriched.summary_de,
        key_features=list(enriched.key_features),
        use_cases=list(enriched.use_cases),
        specs=[SpecOutSchema(name=s.name, value=s.value, unit=s.unit) for s in enriched.specs],
        compatibility=[fact_to_schema(fact) for fact in enriched.compatibility],
        requirements=[requirement_to_schema(req) for req in enriched.requirements],
        completeness=CompletenessSchema(
            score=report.score,
            level=report.level,
            has_description=report.has_description,
            has_attributes=report.has_attributes,
            has_compatibility=report.has_compatibility,
            needs_web=report.needs_web,
            reasons=list(report.reasons),
        ),
        web=WebInfoSchema(status=enriched.web_status, url=enriched.web_url, method=enriched.web_method),
        provenance=[
            FieldProvenanceSchema(
                field=p.field, source=p.source, method=p.method, confidence=p.confidence, detail=p.detail
            )
            for p in enriched.provenance
        ],
        enrichment_model=enriched.enrichment_model,
        prompt_version=enriched.prompt_version,
        validation_notes=list(enriched.validation_notes),
        normalized=normalized_to_schema(product),
    )


def enriched_from_catalog(schema: CatalogProductSchema) -> EnrichedProduct:
    report = schema.completeness
    return EnrichedProduct(
        product=normalized_from_schema(schema.normalized),
        completeness=CompletenessReport(
            score=report.score,
            level=report.level,
            has_description=report.has_description,
            has_attributes=report.has_attributes,
            has_compatibility=report.has_compatibility,
            needs_web=report.needs_web,
            reasons=tuple(report.reasons),
        ),
        category=schema.category,
        product_type=schema.product_type,
        brand=schema.brand,
        summary_en=schema.summary_en,
        summary_de=schema.summary_de,
        key_features=tuple(schema.key_features),
        use_cases=tuple(schema.use_cases),
        specs=tuple(Spec(s.name, s.value, s.unit) for s in schema.specs),
        compatibility=tuple(
            CompatibilityFact(
                dimension=f.dimension,
                raw_value=f.raw_value,
                canonical_value=f.canonical_value,
                status=f.status,
                evidence=_evidence_from_schema(f.evidence),
                confidence=f.confidence,
                method=f.method,
            )
            for f in schema.compatibility
        ),
        requirements=tuple(
            Requirement(
                item=r.item,
                canonical_item=r.canonical_item,
                kind=r.kind,
                necessity=r.necessity,
                alternatives=tuple(r.alternatives),
                evidence=_evidence_from_schema(r.evidence),
                confidence=r.confidence,
                method=r.method,
            )
            for r in schema.requirements
        ),
        provenance=tuple(
            FieldProvenance(p.field, p.source, p.method, p.confidence, p.detail) for p in schema.provenance
        ),
        web_status=schema.web.status,
        web_url=schema.web.url,
        web_method=schema.web.method,
        enrichment_model=schema.enrichment_model,
        prompt_version=schema.prompt_version,
        validation_notes=tuple(schema.validation_notes),
    )


# --- Qdrant payload ----------------------------------------------------------------------

_HUB_KINDS = {RequirementKind.HUB, RequirementKind.GATEWAY}


def payload_from_enriched(enriched: EnrichedProduct, doc_hash: str, embedding_model: str) -> QdrantPayloadSchema:
    product = enriched.product
    required = [r for r in enriched.requirements if r.necessity is Necessity.REQUIRED]
    return QdrantPayloadSchema(
        product_id=product.id,
        title=product.title,
        brand=enriched.brand,
        category=enriched.category,
        product_type=enriched.product_type,
        price=_float(product.price.value),
        currency=product.price.currency,
        is_smart_home=product.is_smart_home,
        ecosystems=list(enriched.supported(Dimension.ECOSYSTEM)),
        voice_assistants=list(enriched.supported(Dimension.VOICE_ASSISTANT)),
        protocols=list(enriched.supported(Dimension.PROTOCOL)),
        mobile_os=list(enriched.supported(Dimension.MOBILE_OS)),
        requirements=sorted({r.canonical_item for r in enriched.requirements if r.canonical_item}),
        requires_hub=any(r.kind in _HUB_KINDS and "standalone" not in r.alternatives for r in required),
        completeness_level=enriched.completeness.level.value,
        image_url=product.image_url,
        source_url=product.source_url,
        doc_hash=doc_hash,
        embedding_model=embedding_model,
    )
