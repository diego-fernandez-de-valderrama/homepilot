import pytest
from catalog_ingestion.domain.enums import FactStatus, RequirementKind

from smart_home_agent.services import compatibility, vocabulary
from smart_home_agent.services.compatibility import CompatibilityService, ProductNotFoundError
from tests.fakes import FakeCatalog, fact, product, requirement

HOMEKIT = vocabulary.term("apple_home")
GOOGLE_HOME = vocabulary.term("google_home")
MATTER = vocabulary.term("matter")
ZIGBEE = vocabulary.term("zigbee")


def test_supported_with_evidence():
    result = compatibility.evaluate(product("1", facts=[fact("apple_home")]), [HOMEKIT])
    check = result.checks[0]
    assert check.status is FactStatus.SUPPORTED
    assert check.evidence and check.evidence[0].text
    assert result.overall is FactStatus.SUPPORTED


def test_explicit_negative_evidence_is_unsupported():
    result = compatibility.evaluate(product("1", facts=[fact("matter", FactStatus.UNSUPPORTED)]), [MATTER])
    assert result.checks[0].status is FactStatus.UNSUPPORTED
    assert result.overall is FactStatus.UNSUPPORTED


def test_missing_data_is_unknown_not_unsupported_and_not_supported():
    result = compatibility.evaluate(product("1", facts=[fact("zigbee")]), [MATTER])
    check = result.checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert check.status is not FactStatus.UNSUPPORTED
    assert check.status is not FactStatus.SUPPORTED
    assert check.evidence == []
    assert any("no information" in note for note in check.notes)


def test_product_without_any_facts_is_unknown():
    result = compatibility.evaluate(product("1"), [HOMEKIT, ZIGBEE])
    assert {c.status for c in result.checks} == {FactStatus.UNKNOWN}
    assert result.overall is FactStatus.UNKNOWN


def test_contradicting_evidence_is_unknown():
    facts = [fact("matter"), fact("matter", FactStatus.UNSUPPORTED)]
    check = compatibility.evaluate(product("1", facts=facts), [MATTER]).checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert any("contradicting" in note for note in check.notes)


def test_siri_does_not_imply_homekit():
    check = compatibility.evaluate(product("1", facts=[fact("apple_siri")]), [HOMEKIT]).checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert any("Apple Siri" in note and "does not confirm" in note for note in check.notes)


def test_google_assistant_does_not_imply_google_home():
    check = compatibility.evaluate(product("1", facts=[fact("google_assistant")]), [GOOGLE_HOME]).checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert any("Google Assistant" in note for note in check.notes)


def test_unmapped_raw_mentions_are_notes_only():
    facts = [fact(None, raw="Matter-fähig über Bridge")]
    check = compatibility.evaluate(product("1", facts=facts), [MATTER]).checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert any("Unmapped catalog mention" in note for note in check.notes)


def test_overall_requires_every_term():
    p = product("1", facts=[fact("apple_home")])
    assert compatibility.evaluate(p, [HOMEKIT, MATTER]).overall is FactStatus.UNKNOWN
    p = product("2", facts=[fact("apple_home"), fact("matter", FactStatus.UNSUPPORTED)])
    assert compatibility.evaluate(p, [HOMEKIT, MATTER]).overall is FactStatus.UNSUPPORTED
    assert compatibility.evaluate(p, []).overall is FactStatus.SUPPORTED  # nothing requested


@pytest.mark.parametrize(
    ("owned", "status"),
    [
        (None, "unverified"),
        ([], "missing"),
        (["philips_hue_bridge"], "missing"),
        (["homematic_ccu3"], "satisfied"),
    ],
)
def test_hub_requirements(owned, status):
    hub = requirement("homematic_ip_access_point", alternatives=["homematic_ip_access_point", "homematic_ccu3"])
    result = compatibility.evaluate(product("1", requirements=[hub]), [], owned)
    assert result.requirements[0].status == status


def test_standalone_alternative_satisfies_hub_requirement():
    hub = requirement("homematic_ip_access_point", alternatives=["homematic_ip_access_point", "standalone"])
    assert compatibility.evaluate(product("1", requirements=[hub]), [], []).requirements[0].status == "satisfied"


def test_professional_installation_flag():
    electrician = requirement("professional_installation", kind=RequirementKind.PROFESSIONAL_INSTALLATION)
    result = compatibility.evaluate(product("1", requirements=[electrician]), [])
    assert result.requires_professional_installation
    assert result.requirements[0].status == "info"


def test_service_reports_unknown_products():
    service = CompatibilityService(FakeCatalog([product("1")]))
    with pytest.raises(ProductNotFoundError):
        service.check(["1", "404"], [HOMEKIT])
