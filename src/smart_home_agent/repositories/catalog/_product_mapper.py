from collections.abc import Sequence
from decimal import Decimal

from catalog_ingestion.schemas.catalog_product import CatalogProductSchema
from catalog_ingestion.schemas.raw_product import RawProductSchema
from catalog_ingestion.storage.postgres.models import CompatibilityRecord, ProductRecord, RequirementRecord
from catalog_ingestion.vocabulary.requirements import term_by_canonical

from smart_home_agent.models import (
    CompatibilityFact,
    Evidence,
    FieldProvenance,
    Product,
    ProductRequirement,
    Spec,
)


class ProductMapper:
    """ORM row -> business model. The only place that turns catalog ORM records into Pydantic models."""

    @staticmethod
    def to_product(record: ProductRecord) -> Product:
        """Typed columns and child tables win; the JSONB document adds the enriched descriptive fields (specs,
        features, provenance), the untouched raw input the version fields (subtitle and the shop's variant options).
        """
        document = CatalogProductSchema.model_validate(record.document)
        raw = RawProductSchema.model_validate(record.raw)
        subtitle = raw.subtitle.strip() or None
        options = [option.strip() for option in raw.variants if option.strip()]
        return Product(
            id=record.id,
            title=record.title,
            brand=record.brand,
            category=record.category,
            category_label_en=document.category_label_en,
            category_label_de=document.category_label_de,
            product_type=record.product_type,
            price=ProductMapper._float(record.price_value),
            currency=record.price_currency,
            original_price=ProductMapper._float(record.original_price),
            price_raw=document.price.raw,
            summary_en=record.summary_en,
            summary_de=record.summary_de,
            source_url=record.source_url,
            subtitle=subtitle,
            variant=ProductMapper.own_variant(subtitle, options),
            variant_options=options,
            ean=record.ean,
            image_url=record.image_url,
            is_smart_home=record.is_smart_home,
            completeness_level=record.completeness_level,
            completeness_score=record.completeness_score,
            key_features=document.key_features,
            use_cases=document.use_cases,
            specs=[Spec(name=s.name, value=s.value, unit=s.unit) for s in document.specs],
            compatibility=[ProductMapper._fact(r) for r in record.compatibility],
            requirements=[ProductMapper._requirement(r) for r in record.requirements],
            attributes=record.attributes,
            provenance=[FieldProvenance.model_validate(p.model_dump()) for p in document.provenance],
            validation_notes=document.validation_notes,
        )

    @staticmethod
    def own_variant(subtitle: str | None, options: Sequence[str]) -> str | None:
        """The option label of this version: the longest shop option that its subtitle contains ("Weiß" in
        "GU10, Dimmbar, RGBW, 350 lm, 4,8 W, Weiß"). None when the subtitle names none of them."""
        text = (subtitle or "").casefold()
        matches = [option for option in options if option.casefold() in text]
        return max(matches, key=len) if matches else None

    @staticmethod
    def _float(value: Decimal | None) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _evidence(record: CompatibilityRecord | RequirementRecord) -> Evidence:
        return Evidence(
            source=record.source,
            text=record.evidence,
            field=record.source_field,
            url=record.source_url,
            method=record.method,
            confidence=record.confidence,
        )

    @staticmethod
    def _fact(record: CompatibilityRecord) -> CompatibilityFact:
        return CompatibilityFact(
            dimension=record.dimension,
            canonical_value=record.canonical_value,
            label=record.label,
            raw_value=record.raw_value,
            status=record.status,
            evidence=ProductMapper._evidence(record),
        )

    @staticmethod
    def _requirement(record: RequirementRecord) -> ProductRequirement:
        term = term_by_canonical(record.canonical_item)
        return ProductRequirement(
            item=record.item,
            canonical_item=record.canonical_item,
            label=term.label if term else record.item,
            kind=record.kind,
            necessity=record.necessity,
            alternatives=list(record.alternatives),
            evidence=ProductMapper._evidence(record),
        )
