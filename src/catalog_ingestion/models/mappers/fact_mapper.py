from catalog_ingestion.models.domain import CompatibilityFact, Evidence, Requirement
from catalog_ingestion.models.schemas import CompatibilityFactSchema, EvidenceSchema, RequirementSchema
from catalog_ingestion.vocabulary import CompatibilityVocabulary


class FactMapper:
    """Compatibility facts and requirements with their evidence."""

    @staticmethod
    def fact_to_schema(fact: CompatibilityFact) -> CompatibilityFactSchema:
        return CompatibilityFactSchema(
            dimension=fact.dimension,
            raw_value=fact.raw_value,
            canonical_value=fact.canonical_value,
            label=CompatibilityVocabulary.label_for(fact.canonical_value),
            status=fact.status,
            evidence=FactMapper._evidence_to_schema(fact.evidence),
            confidence=fact.confidence,
            method=fact.method,
        )

    @staticmethod
    def fact_from_schema(schema: CompatibilityFactSchema) -> CompatibilityFact:
        return CompatibilityFact(
            dimension=schema.dimension,
            raw_value=schema.raw_value,
            canonical_value=schema.canonical_value,
            status=schema.status,
            evidence=FactMapper._evidence_from_schema(schema.evidence),
            confidence=schema.confidence,
            method=schema.method,
        )

    @staticmethod
    def requirement_to_schema(requirement: Requirement) -> RequirementSchema:
        return RequirementSchema(
            item=requirement.item,
            canonical_item=requirement.canonical_item,
            kind=requirement.kind,
            necessity=requirement.necessity,
            alternatives=list(requirement.alternatives),
            evidence=FactMapper._evidence_to_schema(requirement.evidence),
            confidence=requirement.confidence,
            method=requirement.method,
        )

    @staticmethod
    def requirement_from_schema(schema: RequirementSchema) -> Requirement:
        return Requirement(
            item=schema.item,
            canonical_item=schema.canonical_item,
            kind=schema.kind,
            necessity=schema.necessity,
            alternatives=tuple(schema.alternatives),
            evidence=FactMapper._evidence_from_schema(schema.evidence),
            confidence=schema.confidence,
            method=schema.method,
        )

    @staticmethod
    def _evidence_to_schema(evidence: Evidence) -> EvidenceSchema:
        return EvidenceSchema(source=evidence.source, text=evidence.text, field=evidence.field, url=evidence.url)

    @staticmethod
    def _evidence_from_schema(schema: EvidenceSchema) -> Evidence:
        return Evidence(source=schema.source, text=schema.text, field=schema.field, url=schema.url)
