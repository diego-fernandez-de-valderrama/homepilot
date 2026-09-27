from catalog_ingestion.models import Requirement
from catalog_ingestion.preparation import RequirementExtractor
from catalog_ingestion.vocabulary import Necessity, RequirementKind
from tests.conftest import (
    BOSCH_CONTROLLER,
    HOMEMATIC_CCU2,
    HOMEMATIC_OR,
    HOMEMATIC_STANDALONE,
    RING_SUBSCRIPTION,
    SHELLY_ZWAVE,
    SPARSE_MATTER,
    TCL_INSTALLATION,
    load_normalized,
)


def _by_item(product_id: str) -> dict[str | None, Requirement]:
    return {r.canonical_item: r for r in RequirementExtractor.extract(load_normalized(product_id))}


def test_bosch_controller_is_required_hub():
    requirement = _by_item(BOSCH_CONTROLLER)["bosch_smart_home_controller"]
    assert requirement.kind is RequirementKind.HUB
    assert requirement.necessity is Necessity.REQUIRED
    assert "nur in Verbindung mit dem Bosch Smart Home Controller" in requirement.evidence.text


def test_homematic_alternatives():
    requirement = _by_item(HOMEMATIC_OR)["homematic_ip_access_point"]
    assert requirement.alternatives == ("homematic_ip_access_point", "homematic_ccu3", "third_party_partner_solution")


def test_homematic_standalone_alternative():
    requirement = _by_item(HOMEMATIC_STANDALONE)["homematic_ip_access_point"]
    assert "standalone" in requirement.alternatives


def test_ring_subscription_only_for_some_features():
    requirements = _by_item(RING_SUBSCRIPTION)
    assert requirements["ring_subscription"].necessity is Necessity.REQUIRED_FOR_SOME_FEATURES
    assert requirements["wifi_network"].kind is RequirementKind.NETWORK


def test_professional_installation():
    assert _by_item(TCL_INSTALLATION)["professional_installation"].necessity is Necessity.REQUIRED
    assert "professional_installation" in _by_item(SHELLY_ZWAVE)


def test_notes_without_requirement_are_ignored():
    assert _by_item(HOMEMATIC_CCU2) == {}  # "Nicht mehr kompatibel mit der Zentrale CCU2"
    assert "smart_hub" not in _by_item(SHELLY_ZWAVE)  # "Smart Hub nicht enthalten" is not a requirement statement
    assert _by_item(SPARSE_MATTER) == {}
