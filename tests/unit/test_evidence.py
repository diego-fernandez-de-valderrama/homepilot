import pytest

from smart_home_agent.services.evidence import EvidenceService, evidence_for
from smart_home_agent.services.vocabulary import TermResolutionError
from tests.fakes import FakeCatalog, fact, product, requirement

P = product("1", price=54.95, facts=[fact("google_home")], requirements=[requirement("bosch_smart_home_controller")])


def test_price_comes_from_the_catalog():
    result = evidence_for(P, "price")
    assert result.items[0].source == "catalog"
    assert result.items[0].text == "54.95 €"


def test_descriptive_fields_return_stored_provenance():
    result = evidence_for(P, "summary")
    assert result.provenance[0].field == "summary_en"
    assert result.provenance[0].source == "llm"


def test_compatibility_evidence_and_unknown():
    assert evidence_for(P, "Google Home").items[0].text.startswith("evidence for")
    unknown = evidence_for(P, "Matter")
    assert unknown.items == []
    assert "unknown" in (unknown.note or "")


def test_requirements_and_attributes():
    assert evidence_for(P, "requirements").items[0].text.startswith("Hinweise")
    assert evidence_for(P, "Schutzart").items[0].text == "Schutzart: IP20"


def test_unknown_topic_and_ambiguous_topic():
    with pytest.raises(TermResolutionError):
        evidence_for(P, "Teletubby")
    with pytest.raises(TermResolutionError) as info:
        evidence_for(P, "Apple")
    assert info.value.options


def test_service_not_found():
    from smart_home_agent.services.compatibility import ProductNotFoundError

    with pytest.raises(ProductNotFoundError):
        EvidenceService(FakeCatalog([P])).get("404", "price")
