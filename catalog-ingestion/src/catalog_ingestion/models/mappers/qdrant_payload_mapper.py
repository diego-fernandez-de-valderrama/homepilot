from catalog_ingestion.core import Hashing
from catalog_ingestion.models.domain import EnrichedProduct
from catalog_ingestion.models.mappers._number_conversion import NumberConversion
from catalog_ingestion.models.schemas import QdrantPayloadSchema
from catalog_ingestion.vocabulary import Dimension, Necessity, RequirementKind


class QdrantPayloadMapper:
    _HUB_KINDS = frozenset({RequirementKind.HUB, RequirementKind.GATEWAY})

    @staticmethod
    def from_enriched(enriched: EnrichedProduct, doc_hash: str, embedding_model: str) -> QdrantPayloadSchema:
        """The payload of the product's Qdrant point, with `payload_hash` over all other fields."""
        product = enriched.product
        required = [r for r in enriched.requirements if r.necessity is Necessity.REQUIRED]
        payload = QdrantPayloadSchema(
            product_id=product.id,
            title=product.title,
            brand=enriched.brand,
            category=enriched.category,
            product_type=enriched.product_type,
            price=NumberConversion.to_float(product.price.value),
            currency=product.price.currency,
            is_smart_home=product.is_smart_home,
            ecosystems=list(enriched.supported(Dimension.ECOSYSTEM)),
            voice_assistants=list(enriched.supported(Dimension.VOICE_ASSISTANT)),
            protocols=list(enriched.supported(Dimension.PROTOCOL)),
            mobile_os=list(enriched.supported(Dimension.MOBILE_OS)),
            requirements=sorted({r.canonical_item for r in enriched.requirements if r.canonical_item}),
            requires_hub=any(
                r.kind in QdrantPayloadMapper._HUB_KINDS and "standalone" not in r.alternatives for r in required
            ),
            completeness_level=enriched.completeness.level.value,
            image_url=product.image_url,
            source_url=product.source_url,
            doc_hash=doc_hash,
            embedding_model=embedding_model,
        )
        return payload.model_copy(update={"payload_hash": Hashing.sha256_json(payload.model_dump(mode="json"))})
