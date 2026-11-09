from catalog_ingestion.models.domain import CompatibilityClaim, LLMEnrichment, RequirementClaim, Spec
from catalog_ingestion.models.schemas import LLMEnrichmentSchema
from catalog_ingestion.vocabulary import Dimension, FactSource, FactStatus


class LLMEnrichmentMapper:
    @staticmethod
    def from_schema(schema: LLMEnrichmentSchema) -> LLMEnrichment:
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
