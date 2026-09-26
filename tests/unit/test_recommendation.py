from typing import Any

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


def _recommend(**overrides: Any):
    fields: dict[str, Any] = {
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


# Versions of one product share the title (another color, size or pack), like the catalog's sibling products.
WHITE = product("white", title="Thermostat X", price=55.0, facts=[fact("google_home"), fact("wifi")])
ANTHRACITE = product(
    "anthracite", title="Thermostat X", price=65.0, facts=[fact("google_home"), fact("wifi"), fact("matter")]
)
NO_ATTRIBUTES = product("no_attributes", title="Thermostat X", price=55.0)  # Google Home unknown
DOUBLE_PACK = product("double_pack", title="Thermostat X", price=200.0, facts=[fact("google_home")])
OTHER = product("other", title="Thermostat Y", price=60.0, facts=[fact("google_home"), fact("wifi"), fact("matter")])
# The white version leads on relevance (ranking also rewards the extra capability of the anthracite one).
VERSION_SCORES = {"white": 0.9, "anthracite": 0.8, "no_attributes": 0.88, "double_pack": 0.87, "other": 0.86}


def _recommend_versions(products, **overrides: Any):
    fields: dict[str, Any] = {
        "need": "thermostat",
        "category": "heating_control",
        "max_price": 150,
        "must_support": ["google_home"],
    }
    request = RecommendationRequest(**(fields | overrides))
    return services_for(products, VERSION_SCORES).recommendation.recommend(request)


def test_versions_of_one_product_share_one_slot_with_their_own_status():
    result = _recommend_versions([WHITE, ANTHRACITE, NO_ATTRIBUTES, DOUBLE_PACK, OTHER])
    assert [r.product.id for r in result.confirmed] == ["white", "other"]
    assert result.unconfirmed == []  # the product has a confirmed version: no second, unconfirmed entry
    versions = {v.id: (v.status, v.filter_reason) for v in result.confirmed[0].other_versions}
    assert versions == {
        "anthracite": ("confirmed", None),
        "no_attributes": ("unconfirmed", None),
        "double_pack": ("filtered_out", "price"),
    }
    assert result.confirmed[1].other_versions == []
    assert any("other_versions" in note for note in result.notes)


def test_versions_that_were_no_candidates_are_still_checked_against_the_request():
    # Only the white version is found by the search; the anthracite one is a structured Matter match.
    services = services_for([WHITE, ANTHRACITE, NO_ATTRIBUTES], {"white": 0.9})
    request = RecommendationRequest(need="thermostat", category="heating_control", must_support=["matter"])
    result = services.recommendation.recommend(request)
    [entry] = result.confirmed
    assert entry.product.id == "anthracite"
    assert result.unconfirmed == []  # the white version is not listed again as a separate product
    assert {v.id: v.status for v in entry.other_versions} == {"white": "unconfirmed", "no_attributes": "unconfirmed"}


def test_a_version_of_the_best_match_is_never_its_upsell():
    result = _recommend_versions([WHITE, ANTHRACITE])
    assert result.best_match == "white"
    assert result.upsell is None  # pricier and with more confirmed capabilities, but the same product
    assert result.upsell_blockers == {"other_version_of_best": 1}


def test_the_upsell_version_takes_its_products_slot():
    # Best match: white (X). The cheaper Y version ranks above the Y version that is the upsell.
    small = product("small", title="Thermostat Y", price=58.0, facts=[fact("google_home")])
    scores = {"white": 0.99, "small": 0.95, "other": 0.86}
    services = services_for([WHITE, small, OTHER], scores)
    request = RecommendationRequest(need="thermostat", category="heating_control", must_support=["google_home"])
    result = services.recommendation.recommend(request)
    assert result.upsell is not None and result.upsell.product_id == "other"
    titles = [r.product.title for r in result.confirmed]
    assert len(titles) == len(set(titles))
    assert "other" in {r.product.id for r in result.confirmed}


def test_stated_ownership_prefers_the_product_that_fits_the_customers_hub():
    hue = product("hue", price=40.0, facts=[fact("google_home")], requirements=[requirement("philips_hue_bridge")])
    bosch = product(
        "bosch", price=45.0, facts=[fact("google_home")], requirements=[requirement("bosch_smart_home_controller")]
    )
    services = services_for([hue, bosch], {"hue": 0.9, "bosch": 0.85})

    def best(owned: list[str] | None) -> str | None:
        request = RecommendationRequest(need="radiator thermostat", must_support=["google_home"], owned_devices=owned)
        return services.recommendation.recommend(request).best_match

    assert best(None) == "hue"
    assert best(["philips_hue_bridge"]) == "hue"
    assert best(["bosch_smart_home_controller"]) == "bosch"
