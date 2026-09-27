from typing import Any

from catalog_ingestion.database.records import CompatibilityRecord, RequirementRecord, WebPageRecord
from catalog_ingestion.models import CompatibilityFact, EnrichedProduct, Requirement, WebPage
from catalog_ingestion.vocabulary import CompatibilityVocabulary


class RecordBuilder:
    """Domain dataclasses <-> ORM records for the parts `PostgresRepository` writes column by column."""

    @staticmethod
    def compatibility(fact: CompatibilityFact) -> CompatibilityRecord:
        return CompatibilityRecord(
            dimension=fact.dimension.value,
            canonical_value=fact.canonical_value,
            label=CompatibilityVocabulary.label_for(fact.canonical_value),
            raw_value=fact.raw_value,
            status=fact.status.value,
            source=fact.evidence.source.value,
            source_field=fact.evidence.field,
            source_url=fact.evidence.url,
            evidence=fact.evidence.text,
            confidence=fact.confidence,
            method=fact.method.value,
        )

    @staticmethod
    def requirement(requirement: Requirement) -> RequirementRecord:
        return RequirementRecord(
            item=requirement.item,
            canonical_item=requirement.canonical_item,
            kind=requirement.kind.value,
            necessity=requirement.necessity.value,
            alternatives=list(requirement.alternatives),
            source=requirement.evidence.source.value,
            source_field=requirement.evidence.field,
            source_url=requirement.evidence.url,
            evidence=requirement.evidence.text,
            confidence=requirement.confidence,
            method=requirement.method.value,
        )

    @staticmethod
    def attributes_json(enriched: EnrichedProduct) -> dict[str, Any]:
        """`{section: {key: value}}` for ad-hoc queries."""
        sections: dict[str, dict[str, str]] = {}
        for entry in enriched.product.attributes.entries:
            sections.setdefault(entry.section, {})[entry.key] = entry.value
        return sections

    @staticmethod
    def web_page_record(product_id: str, page: WebPage) -> WebPageRecord:
        return WebPageRecord(
            url=page.url,
            product_id=product_id,
            ok=page.ok,
            method=page.method,
            http_status=page.http_status,
            text=page.text,
            error=page.error,
            fetched_at=page.fetched_at,
        )

    @staticmethod
    def web_page(record: WebPageRecord) -> WebPage:
        return WebPage(
            url=record.url,
            ok=record.ok,
            method=record.method,
            http_status=record.http_status,
            text=record.text,
            error=record.error,
            fetched_at=record.fetched_at,
        )
