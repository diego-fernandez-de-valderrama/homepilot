from smart_home_agent.models import RequirementCheck
from smart_home_agent.services import AccessoryService, CompatibilityEvaluator
from tests.fakes import FakeCatalog, product, requirement

ACCESS_POINT = product(
    "ap", title="Homematic IP Steuerzentrale Access Point HmIP-HAP", category="hub_gateway", price=49.1
)
ACCESS_POINT_2 = product("ap2", title="Homematic IP Steuerzentrale Access Point 2", category="hub_gateway", price=59.95)
STARTER_SET = product(
    "set", title="Homematic IP Starter-Set Heizen mit Access Point", category="hub_gateway", price=39.0
)
HUE_BRIDGE = product("bridge", title="Philips Hue Steuerzentrale Bridge", category="hub_gateway", price=49.69)
NOT_A_HUB = product("thermo", title="Homematic IP Access Point Thermostat", category="heating_control", price=5.0)
THERMOSTAT = product("t", price=60.0, requirements=[requirement("homematic_ip_access_point")])

SERVICE = AccessoryService(FakeCatalog([ACCESS_POINT, ACCESS_POINT_2, STARTER_SET, HUE_BRIDGE, NOT_A_HUB, THERMOSTAT]))


def _checks(owned: list[str] | None) -> list[RequirementCheck]:
    return [CompatibilityEvaluator.check_requirement(r, owned) for r in THERMOSTAT.requirements]


def test_cheapest_bare_hub_of_the_right_category_is_chosen():
    hub = SERVICE.hub_for("homematic_ip_access_point")
    assert hub is not None and hub.id == "ap"  # not the cheaper starter set, not another category
    bridge = SERVICE.hub_for("philips_hue_bridge")
    assert bridge is not None and bridge.id == "bridge"


def test_no_suggestion_without_a_safe_mapping():
    assert SERVICE.hub_for("smart_hub") is None
    assert SERVICE.hub_for("bosch_smart_home_controller") is None  # mapped, but not in this catalog


def test_accessory_status_follows_ownership():
    [unverified] = SERVICE.for_product(THERMOSTAT, _checks(None))
    assert (unverified.status, unverified.product_id, unverified.bundle_total) == ("unverified", "ap", 109.1)
    [missing] = SERVICE.for_product(THERMOSTAT, _checks(["philips_hue_bridge"]))
    assert missing.status == "missing"
    assert SERVICE.for_product(THERMOSTAT, _checks(["homematic_ip_access_point"])) == []


def test_hub_prices_and_availability_are_read_fresh():
    catalog = FakeCatalog([ACCESS_POINT, ACCESS_POINT_2, THERMOSTAT])
    service = AccessoryService(catalog)
    first = service.hub_for("homematic_ip_access_point")
    assert first is not None and first.id == "ap"
    catalog.products["ap"] = ACCESS_POINT.model_copy(update={"price": 79.0})  # re-ingest: new price
    hub = service.hub_for("homematic_ip_access_point")
    assert hub is not None and hub.id == "ap2"
    del catalog.products["ap2"]  # deactivated
    hub = service.hub_for("homematic_ip_access_point")
    assert hub is not None and (hub.id, hub.price) == ("ap", 79.0)
