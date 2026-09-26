from smart_home_agent.services import ranking
from tests.fakes import fact, product

BASIC = product("basic", price=50.0, facts=[fact("google_home"), fact("wifi")])
PREMIUM = product("premium", price=90.0, facts=[fact("google_home"), fact("wifi"), fact("matter"), fact("apple_home")])
PRICEY = product("pricey", price=300.0, facts=[fact("google_home"), fact("wifi"), fact("matter"), fact("apple_home")])
SIDEGRADE = product("sidegrade", price=80.0, facts=[fact("google_home"), fact("zigbee")])  # not a superset
OTHER_TYPE = product(
    "floor", price=95.0, product_type="Room thermostat", facts=[fact("google_home"), fact("wifi"), fact("matter")]
)


def _ranked(products, scores: dict[str, float | None] | None = None):
    if not scores:
        scores = {p.id: 0.8 for p in products}
    return ranking.rank(ranking.build_candidates(products, scores, "radiator thermostat"))


def test_ranking_is_relevance_first_and_price_neutral():
    ranked = _ranked([PREMIUM, BASIC], {"premium": 0.5, "basic": 0.9})
    assert ranked[0].product.id == "basic"


def test_type_match_helps_the_right_product_type():
    adapter = product("adapter", product_type="Valve adapter", title="Adapter")
    ranked = _ranked([adapter, BASIC], {"adapter": 0.8, "basic": 0.8})
    assert ranked[0].product.id == "basic"
    assert not ranked[1].type_match


def test_upsell_needs_more_capabilities_within_budget():
    ranked = _ranked([BASIC, PREMIUM, PRICEY, SIDEGRADE])
    best = next(c for c in ranked if c.product.id == "basic")
    upsell = ranking.select_upsell(ranked, best, max_price=150, min_relative_relevance=0.75)
    assert upsell is not None
    assert upsell.product_id == "premium"
    assert upsell.price <= 150
    assert upsell.price_difference == 40.0
    assert any("Matter" in r for r in upsell.upgrade_reasons)
    assert any("Apple Home" in r for r in upsell.upgrade_reasons)


def test_upsell_never_exceeds_budget():
    ranked = _ranked([BASIC, PRICEY])
    best = next(c for c in ranked if c.product.id == "basic")
    assert ranking.select_upsell(ranked, best, max_price=150, min_relative_relevance=0.75) is None


def test_no_upsell_without_strictly_more_capabilities_or_for_another_product_type():
    ranked = _ranked([BASIC, SIDEGRADE, OTHER_TYPE])
    best = next(c for c in ranked if c.product.id == "basic")
    assert ranking.select_upsell(ranked, best, max_price=None, min_relative_relevance=0.75) is None


def test_no_upsell_when_far_less_relevant():
    ranked = _ranked([BASIC, PREMIUM], {"basic": 0.9, "premium": 0.3})
    best = next(c for c in ranked if c.product.id == "basic")
    assert ranking.select_upsell(ranked, best, max_price=None, min_relative_relevance=0.75) is None


def test_same_product_type_rule():
    assert ranking.same_product_type(
        product("1", product_type="Radiator thermostat"), product("2", product_type="Smart radiator thermostat")
    )
    assert not ranking.same_product_type(
        product("1", product_type="Radiator thermostat"), product("2", product_type="Room thermostat")
    )
    assert not ranking.same_product_type(product("1", product_type=None), product("2"))


def test_upsell_rejection_names_the_failing_rule():
    ranked = _ranked([BASIC, PREMIUM, PRICEY, SIDEGRADE, OTHER_TYPE, product("cheaper", price=10.0)])
    best = next(c for c in ranked if c.product.id == "basic")
    reasons = {c.product.id: ranking.upsell_rejection(c, best, 150, 0.75) for c in ranked}
    assert reasons == {
        "basic": "best_match",
        "premium": None,
        "pricey": "over_budget",
        "sidegrade": "not_capability_superset",
        "floor": "other_product_type",
        "cheaper": "not_pricier",
    }
    assert ranking.upsell_blockers(ranked, best, 150, 0.75) == {
        "over_budget": 1,
        "not_capability_superset": 1,
        "other_product_type": 1,
        "not_pricier": 1,
    }
