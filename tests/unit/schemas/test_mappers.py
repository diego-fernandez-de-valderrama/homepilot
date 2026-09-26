import dataclasses

import pytest

from catalog_ingestion.domain.enums import WebStatus
from catalog_ingestion.extraction.compatibility import extract_compatibility
from catalog_ingestion.extraction.requirements import extract_requirements
from catalog_ingestion.quality.completeness import assess_completeness
from catalog_ingestion.schemas.catalog_product import CatalogProductSchema
from catalog_ingestion.schemas.mappers import enriched_from_catalog, enriched_to_catalog, payload_from_enriched
from catalog_ingestion.validation.validator import Validator
from tests.conftest import load_normalized
from tests.fakes import empty_llm


def _enriched(product_id: str):
    product = load_normalized(product_id)
    facts = extract_compatibility(product)
    return Validator().validate(
        product, assess_completeness(product, facts), facts, extract_requirements(product),
        WebStatus.NOT_NEEDED, None, empty_llm(summary_en="Summary", use_cases=("Use",)), "m", "v",
    )  # fmt: skip


def test_catalog_round_trip_for_all_fixtures(all_fixture_ids):
    for product_id in all_fixture_ids:
        enriched = _enriched(product_id)
        json_document = enriched_to_catalog(enriched).model_dump(mode="json")
        restored = enriched_from_catalog(CatalogProductSchema.model_validate(json_document))
        assert restored == enriched, product_id


def test_domain_models_are_immutable():
    enriched = _enriched("32391327")
    with pytest.raises(dataclasses.FrozenInstanceError):
        enriched.brand = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        enriched.product.price.value = None  # type: ignore[misc]


def test_qdrant_payload_contains_filter_fields():
    payload = payload_from_enriched(_enriched("25181740"), doc_hash="h", embedding_model="m@8")
    assert payload.ecosystems == ["apple_home", "bosch_smart_home"]
    assert payload.voice_assistants == ["amazon_alexa", "apple_siri", "google_assistant"]
    assert payload.requirements == ["bosch_smart_home_controller"]
    assert payload.requires_hub is True
    assert payload.category == "alarm_system"  # from the URL slug smart-home-alarmanlagen


def test_standalone_alternative_means_no_hub_required():
    payload = payload_from_enriched(_enriched("27103041"), doc_hash="h", embedding_model="m@8")
    assert payload.requires_hub is False
