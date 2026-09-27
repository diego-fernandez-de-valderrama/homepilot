import dataclasses

import pytest

from catalog_ingestion.enrichment import Validator
from catalog_ingestion.models import CatalogProductMapper, CatalogProductSchema, QdrantPayloadMapper
from catalog_ingestion.preparation import CompatibilityExtractor, CompletenessAssessor, RequirementExtractor
from catalog_ingestion.vocabulary import WebStatus
from tests.conftest import load_normalized
from tests.fakes import empty_llm


def _enriched(product_id: str):
    product = load_normalized(product_id)
    facts = CompatibilityExtractor.extract(product)
    return Validator().validate(
        product, CompletenessAssessor.assess(product, facts), facts, RequirementExtractor.extract(product),
        WebStatus.NOT_NEEDED, None, empty_llm(summary_en="Summary", use_cases=("Use",)), "m", "v",
    )  # fmt: skip


def test_catalog_round_trip_for_all_fixtures(all_fixture_ids):
    for product_id in all_fixture_ids:
        enriched = _enriched(product_id)
        json_document = CatalogProductMapper.to_schema(enriched).model_dump(mode="json")
        restored = CatalogProductMapper.from_schema(CatalogProductSchema.model_validate(json_document))
        assert restored == enriched, product_id


def test_domain_models_are_immutable():
    enriched = _enriched("32391327")
    with pytest.raises(dataclasses.FrozenInstanceError):
        enriched.brand = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        enriched.product.price.value = None  # type: ignore[misc]


def test_qdrant_payload_contains_filter_fields():
    payload = QdrantPayloadMapper.from_enriched(_enriched("25181740"), doc_hash="h", embedding_model="m@8")
    assert payload.ecosystems == ["apple_home", "bosch_smart_home"]
    assert payload.voice_assistants == ["amazon_alexa", "apple_siri", "google_assistant"]
    assert payload.requirements == ["bosch_smart_home_controller"]
    assert payload.requires_hub is True
    assert payload.category == "alarm_system"  # from the URL slug smart-home-alarmanlagen


def test_standalone_alternative_means_no_hub_required():
    payload = QdrantPayloadMapper.from_enriched(_enriched("27103041"), doc_hash="h", embedding_model="m@8")
    assert payload.requires_hub is False
