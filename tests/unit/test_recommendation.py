from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models.recommendation import RecommendationRequest
from tests.fakes import fact, product, requirement, services_for

CONFIRMED_CHEAP = product("cheap", price=55.0, facts=[fact("google_home"), fact("wifi")])
CONFIRMED_PREMIUM = product("premium", price=120.0, facts=[fact("google_home"), fact("wifi"), fact("matter")])
OVER_BUDGET = product(
    "expensive", price=165.0, facts=[fact("google_home"), fact("wifi"), fact("matter"), fact("apple_home")]
)
ASSISTANT_ONLY = product("assistant", price=60.0, facts=[fact("google_assistant")])  # Google Home unknown
NEGATIVE = product(
    "negative",
    price=40.0,
    facts=[fact("google_home", FactStatus.UNSUPPORTED), fact("zigbee"), fact("wifi"), fact("matter")],
)
PLUG = product("plug", category="smart_plug", product_type="Smart plug", price=20.0, facts=[fact("google_home")])

ALL = [CONFIRMED_CHEAP, CONFIRMED_PREMIUM, OVER_BUDGET, ASSISTANT_ONLY, NEGATIVE, PLUG]


def _recommend(**overrides):
    fields = {
        "need": "radiator thermostat",
        "category": "heating_control",
        "max_price": 150,
        "must_support": ["google_home"],
    }
    request = RecommendationRequest(**(fields | overrides))
    scores = {"cheap": 0.9, "premium": 0.85, "expensive": 0.95, "assistant": 0.99, "negative": 0.99, "plug": 0.5}
    return services_for(ALL, scores).recommendation.recommend(request)


def test_only_confirmed_products_can_be_recommended():
    result = _recommend()
    confirmed = [r.product.id for r in result.confirmed]
    assert set(confirmed) == {"cheap", "premium"}
    assert all(r.compatibility is FactStatus.SUPPORTED for r in result.confirmed)
    assert result.best_match in confirmed


def test_unknown_compatibility_is_unconfirmed_not_recommended_not_excluded():
    result = _recommend()
    assert [r.product.id for r in result.unconfirmed] == ["assistant"]
    assert result.unconfirmed[0].compatibility is FactStatus.UNKNOWN
    assert any("Google Assistant" in note for check in result.unconfirmed[0].checks for note in check.notes)


def test_hard_constraints_are_applied_before_ranking():
    result = _recommend()
    assert result.excluded == {"price": 1, "category": 1, "unsupported": 1}
    ids = {r.product.id for r in (*result.confirmed, *result.unconfirmed)}
    assert not ids & {"expensive", "plug", "negative"}


def test_compatibility_gate_precedes_upselling():
    result = _recommend()
    assert result.upsell is not None
    assert result.upsell.product_id == "premium"  # compatible and within budget
    assert result.upsell.product_id not in {"negative", "assistant", "expensive"}
    assert result.upsell.price <= 150
    assert any("Matter" in reason for reason in result.upsell.upgrade_reasons)


def test_without_budget_higher_priced_products_stay_eligible():
    result = _recommend(max_price=None)
    assert "expensive" in {r.product.id for r in result.confirmed}
    best = next(r for r in result.confirmed if r.product.id == result.best_match)
    if result.upsell:  # an upsell is always pricier and better equipped than the best match
        assert result.upsell.price > (best.product.price or 0)


def test_no_confirmed_products_means_no_best_match_and_no_upsell():
    result = _recommend(must_support=["google_home", "z_wave"])
    assert result.confirmed == []
    assert result.best_match is None
    assert result.upsell is None
    assert any("do not present any product as compatible" in note for note in result.notes)


def test_structured_matches_are_found_even_when_semantic_search_misses_them():
    from smart_home_agent.config import AgentSettings
    from smart_home_agent.container import Services
    from tests.fakes import FakeCatalog, FakeIndex

    index = FakeIndex({"cheap": 0.9, "premium": 0.4}, hidden=["premium"])
    services = Services.create(FakeCatalog([CONFIRMED_CHEAP, CONFIRMED_PREMIUM]), index, AgentSettings())
    request = RecommendationRequest(need="thermostat", category="heating_control", must_support=["google_home"])
    result = services.recommendation.recommend(request)
    assert {r.product.id for r in result.confirmed} == {"cheap", "premium"}
    assert next(r for r in result.confirmed if r.product.id == "premium").relevance > 0


def test_required_hub_is_flagged():
    hub_product = product(
        "hub", price=70.0, facts=[fact("google_home")], requirements=[requirement("bosch_smart_home_controller")]
    )
    services = services_for([hub_product])
    request = RecommendationRequest(
        need="thermostat", must_support=["google_home"], owned_devices=["philips_hue_bridge"]
    )
    result = services.recommendation.recommend(request)
    assert result.confirmed[0].missing_requirements == ["Bosch Smart Home Controller"]


BOSCH_CONTROLLER = product(
    "controller", title="Bosch Smart Home Controller II", category="hub_gateway", product_type="Controller", price=78.0
)


def test_required_hub_is_offered_as_accessory_with_bundle_total():
    thermostat = product(
        "bosch", price=70.0, facts=[fact("google_home")], requirements=[requirement("bosch_smart_home_controller")]
    )
    services = services_for([thermostat, BOSCH_CONTROLLER])
    request = RecommendationRequest(need="thermostat", category="heating_control", must_support=["google_home"])
    [accessory] = services.recommendation.recommend(request).accessories
    assert (accessory.for_product_id, accessory.product_id) == ("bosch", "controller")
    assert (accessory.status, accessory.bundle_total) == ("unverified", 148.0)

    owned = request.model_copy(update={"owned_devices": ["bosch_smart_home_controller"]})
    assert services.recommendation.recommend(owned).accessories == []


def test_upsell_that_needs_an_extra_hub_is_skipped():
    hub_premium = product(
        "premium",
        price=120.0,
        facts=[fact("google_home"), fact("wifi"), fact("matter")],
        requirements=[requirement("bosch_smart_home_controller")],
    )
    services = services_for([CONFIRMED_CHEAP, hub_premium], {"cheap": 0.9, "premium": 0.85})
    request = RecommendationRequest(
        need="radiator thermostat", category="heating_control", must_support=["google_home"]
    )
    result = services.recommendation.recommend(request)
    assert result.best_match == "cheap"
    assert result.upsell is None
    assert result.upsell_blockers == {"needs_extra_hub": 1}
    assert "upsell_blockers" not in result.model_dump()  # diagnostics never reach the model
