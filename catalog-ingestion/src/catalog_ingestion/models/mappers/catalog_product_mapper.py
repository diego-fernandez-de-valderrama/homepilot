from catalog_ingestion.models.domain import CompletenessReport, EnrichedProduct, FieldProvenance, Spec
from catalog_ingestion.models.mappers.fact_mapper import FactMapper
from catalog_ingestion.models.mappers.normalized_product_mapper import NormalizedProductMapper
from catalog_ingestion.models.schemas import (
    CatalogProductSchema,
    CompletenessSchema,
    FieldProvenanceSchema,
    SpecOutSchema,
    WebInfoSchema,
)
from catalog_ingestion.vocabulary import CategoryVocabulary


class CatalogProductMapper:
    """`EnrichedProduct` <-> `CatalogProductSchema` (the `products.document` JSONB read by the agent)."""

    @staticmethod
    def to_schema(enriched: EnrichedProduct) -> CatalogProductSchema:
        product = enriched.product
        category = CategoryVocabulary.by_key(enriched.category)
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
            price=NormalizedProductMapper.price_to_schema(product.price),
            summary_en=enriched.summary_en,
            summary_de=enriched.summary_de,
            key_features=list(enriched.key_features),
            use_cases=list(enriched.use_cases),
            specs=[SpecOutSchema(name=s.name, value=s.value, unit=s.unit) for s in enriched.specs],
            compatibility=[FactMapper.fact_to_schema(fact) for fact in enriched.compatibility],
            requirements=[FactMapper.requirement_to_schema(req) for req in enriched.requirements],
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
            normalized=NormalizedProductMapper.to_schema(product),
        )

    @staticmethod
    def from_schema(schema: CatalogProductSchema) -> EnrichedProduct:
        report = schema.completeness
        return EnrichedProduct(
            product=NormalizedProductMapper.from_schema(schema.normalized),
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
            compatibility=tuple(FactMapper.fact_from_schema(f) for f in schema.compatibility),
            requirements=tuple(FactMapper.requirement_from_schema(r) for r in schema.requirements),
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
