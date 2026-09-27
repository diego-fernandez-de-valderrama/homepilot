import pytest
from catalog_ingestion.domain.enums import FactStatus, Necessity, RequirementKind

from smart_home_agent.services import CompatibilityEvaluator, CompatibilityService, ProductNotFoundError, Vocabulary
from tests.fakes import FakeCatalog, fact, product, requirement

HOMEKIT = Vocabulary.term("apple_home")
GOOGLE_HOME = Vocabulary.term("google_home")
MATTER = Vocabulary.term("matter")
ZIGBEE = Vocabulary.term("zigbee")


def test_supported_with_evidence():
    result = CompatibilityEvaluator.evaluate(product("1", facts=[fact("apple_home")]), [HOMEKIT])
    check = result.checks[0]
    assert check.status is FactStatus.SUPPORTED
    assert check.evidence and check.evidence[0].text
    assert result.overall is FactStatus.SUPPORTED


def test_explicit_negative_evidence_is_unsupported():
    result = CompatibilityEvaluator.evaluate(product("1", facts=[fact("matter", FactStatus.UNSUPPORTED)]), [MATTER])
    assert result.checks[0].status is FactStatus.UNSUPPORTED
    assert result.overall is FactStatus.UNSUPPORTED


def test_missing_data_is_unknown_not_unsupported_and_not_supported():
    result = CompatibilityEvaluator.evaluate(product("1", facts=[fact("zigbee")]), [MATTER])
    check = result.checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert check.status is not FactStatus.UNSUPPORTED
    assert check.status is not FactStatus.SUPPORTED
    assert check.evidence == []
    assert any("no information" in note for note in check.notes)


def test_product_without_any_facts_is_unknown():
    result = CompatibilityEvaluator.evaluate(product("1"), [HOMEKIT, ZIGBEE])
    assert {c.status for c in result.checks} == {FactStatus.UNKNOWN}
    assert result.overall is FactStatus.UNKNOWN


def test_contradicting_evidence_is_unknown():
    facts = [fact("matter"), fact("matter", FactStatus.UNSUPPORTED)]
    check = CompatibilityEvaluator.evaluate(product("1", facts=facts), [MATTER]).checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert any("contradicting" in note for note in check.notes)


def test_siri_does_not_imply_homekit():
    check = CompatibilityEvaluator.evaluate(product("1", facts=[fact("apple_siri")]), [HOMEKIT]).checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert any("Apple Siri" in note and "does not confirm" in note for note in check.notes)


def test_google_assistant_does_not_imply_google_home():
    check = CompatibilityEvaluator.evaluate(product("1", facts=[fact("google_assistant")]), [GOOGLE_HOME]).checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert any("Google Assistant" in note for note in check.notes)


def test_unmapped_raw_mentions_are_notes_only():
    facts = [fact(None, raw="Matter-fähig über Bridge")]
    check = CompatibilityEvaluator.evaluate(product("1", facts=facts), [MATTER]).checks[0]
    assert check.status is FactStatus.UNKNOWN
    assert any("Unmapped catalog mention" in note for note in check.notes)


def test_overall_requires_every_term():
    p = product("1", facts=[fact("apple_home")])
    assert CompatibilityEvaluator.evaluate(p, [HOMEKIT, MATTER]).overall is FactStatus.UNKNOWN
    p = product("2", facts=[fact("apple_home"), fact("matter", FactStatus.UNSUPPORTED)])
    assert CompatibilityEvaluator.evaluate(p, [HOMEKIT, MATTER]).overall is FactStatus.UNSUPPORTED
    assert CompatibilityEvaluator.evaluate(p, []).overall is FactStatus.SUPPORTED  # nothing requested


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
    result = CompatibilityEvaluator.evaluate(product("1", requirements=[hub]), [], owned)
    assert result.requirements[0].status == status


def test_standalone_alternative_satisfies_hub_requirement():
    hub = requirement("homematic_ip_access_point", alternatives=["homematic_ip_access_point", "standalone"])
    assert (
        CompatibilityEvaluator.evaluate(product("1", requirements=[hub]), [], []).requirements[0].status == "satisfied"
    )


def test_professional_installation_flag():
    electrician = requirement("professional_installation", kind=RequirementKind.PROFESSIONAL_INSTALLATION)
    result = CompatibilityEvaluator.evaluate(product("1", requirements=[electrician]), [])
    assert result.requires_professional_installation
    assert result.requirements[0].status == "info"


def test_service_reports_unknown_products():
    service = CompatibilityService(FakeCatalog([product("1")]))
    with pytest.raises(ProductNotFoundError):
        service.check(["1", "404"], [HOMEKIT])


def test_service_without_accessory_service_offers_no_hub():
    dimmer = product("1", requirements=[requirement("bosch_smart_home_controller")])
    [result] = CompatibilityService(FakeCatalog([dimmer])).check(["1"], [])
    assert result.requirements[0].status == "unverified"
    assert result.accessories == []


def test_needed_hubs_and_owned_hub_fit_follow_the_stated_ownership():
    hub = product("1", requirements=[requirement("philips_hue_bridge")])
    assert CompatibilityEvaluator.evaluate(hub, [], None).needed_hubs() == {"philips_hue_bridge"}
    assert CompatibilityEvaluator.evaluate(hub, [], []).needed_hubs() == {"philips_hue_bridge"}
    owned = CompatibilityEvaluator.evaluate(hub, [], ["philips_hue_bridge"])
    assert owned.needed_hubs() == frozenset()
    assert owned.uses_owned_hub
    assert "uses_owned_hub" not in owned.model_dump()  # a ranking signal, not tool output
    assert not CompatibilityEvaluator.evaluate(hub, [], None).uses_owned_hub
    optional = product(
        "2", requirements=[requirement("philips_hue_bridge", necessity=Necessity.REQUIRED_FOR_SOME_FEATURES)]
    )
    assert CompatibilityEvaluator.evaluate(optional, [], ["philips_hue_bridge"]).uses_owned_hub
    assert not CompatibilityEvaluator.evaluate(product("3"), [], ["philips_hue_bridge"]).uses_owned_hub


def test_only_an_explicit_standalone_alternative_means_stand_alone():
    either = requirement("philips_hue_bridge", alternatives=["philips_hue_bridge", "standalone"])
    assert product("1", requirements=[either]).runs_standalone
    assert not product("2", requirements=[requirement("philips_hue_bridge")]).runs_standalone
    assert not product("3").runs_standalone  # no hub row: unknown, not stand-alone
