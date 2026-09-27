from catalog_ingestion.enrichment import Validator
from catalog_ingestion.indexing import RetrievalDocumentBuilder
from catalog_ingestion.preparation import CompatibilityExtractor, CompletenessAssessor, RequirementExtractor
from catalog_ingestion.vocabulary import WebStatus
from tests.conftest import BOSCH_CONTROLLER, HOMEMATIC_OR, SPARSE_MATTER, load_normalized
from tests.fakes import empty_llm


def _document(product_id: str, llm=None):
    product = load_normalized(product_id)
    facts = CompatibilityExtractor.extract(product)
    enriched = Validator().validate(
        product, CompletenessAssessor.assess(product, facts), facts, RequirementExtractor.extract(product),
        WebStatus.NOT_NEEDED, None, llm, None, None,
    )  # fmt: skip
    return RetrievalDocumentBuilder.build(enriched)


def test_document_is_semantic_text_not_json():
    text = _document(BOSCH_CONTROLLER).text
    assert not text.lstrip().startswith("{")
    assert "Product: Bosch Smart Home Bewegungsmelder" in text
    assert "Category: Alarm system (Alarmanlage)" in text
    assert "Smart home ecosystems and standards: Apple Home (HomeKit), Bosch Smart Home" in text
    assert "Voice assistants: Amazon Alexa, Apple Siri, Google Assistant" in text
    assert "Bosch Smart Home Controller - required" in text


def test_requirement_alternatives_are_listed():
    text = _document(HOMEMATIC_OR).text
    assert "Homematic IP Access Point - required (or: Homematic Zentrale CCU3" in text


def test_llm_fields_are_included():
    llm = empty_llm(summary_en="A window contact.", use_cases=("Window monitoring",), key_features=("Matter support",))
    text = _document(SPARSE_MATTER, llm).text
    assert "Summary: A window contact." in text
    assert "Use cases:\n- Window monitoring" in text


def test_doc_hash_is_stable_and_content_sensitive():
    assert _document(SPARSE_MATTER).doc_hash == _document(SPARSE_MATTER).doc_hash
    assert _document(SPARSE_MATTER).doc_hash != _document(SPARSE_MATTER, empty_llm(summary_en="x")).doc_hash
