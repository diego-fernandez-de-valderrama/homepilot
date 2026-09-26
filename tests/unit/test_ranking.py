from smart_home_agent.services import compatibility, ranking
from tests.fakes import fact, product, requirement

BASIC = product("basic", price=50.0, facts=[fact("google_home"), fact("wifi")])
PREMIUM = product("premium", price=90.0, facts=[fact("google_home"), fact("wifi"), fact("matter"), fact("apple_home")])
PRICEY = product("pricey", price=300.0, facts=[fact("google_home"), fact("wifi"), fact("matter"), fact("apple_home")])
SIDEGRADE = product("sidegrade", price=80.0, facts=[fact("google_home"), fact("zigbee")])  # loses Wi-Fi
SAME = product("same", price=70.0, facts=[fact("google_home"), fact("wifi")])  # pricier, nothing more
OTHER_TYPE = product(
    "floor", price=95.0, product_type="Room thermostat", facts=[fact("google_home"), fact("wifi"), fact("matter")]
)


def _ranked(products, scores: dict[str, float | None] | None = None, owned_devices: list[str] | None = None):
    if not scores:
        scores = {p.id: 0.8 for p in products}
    results = {p.id: compatibility.evaluate(p, [], owned_devices) for p in products}
    return ranking.rank(ranking.build_candidates(products, scores, "radiator thermostat", results))


def _best(ranked, product_id: str = "basic"):
    return next(c for c in ranked if c.product.id == product_id)


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
    ranked = _ranked([BASIC, PREMIUM, PRICEY, SIDEGRADE, SAME, OTHER_TYPE, product("cheaper", price=10.0)])
    best = next(c for c in ranked if c.product.id == "basic")
    reasons = {c.product.id: ranking.upsell_rejection(c, best, 150, 0.75) for c in ranked}
    assert reasons == {
        "basic": "best_match",
        "premium": None,
        "pricey": "over_budget",
        "sidegrade": "loses_capability",
        "same": "no_advantage",
        "floor": "other_product_type",
        "cheaper": "not_pricier",
    }
    assert ranking.upsell_blockers(ranked, best, 150, 0.75) == {
        "over_budget": 1,
        "loses_capability": 1,
        "no_advantage": 1,
        "other_product_type": 1,
        "not_pricier": 1,
    }


def test_a_confirmed_phone_platform_is_an_upgrade_reason():
    app = product("app", price=70.0, facts=[fact("google_home"), fact("wifi"), fact("ios")])
    ranked = _ranked([BASIC, app])
    upsell = ranking.select_upsell(ranked, _best(ranked), max_price=None, min_relative_relevance=0.75)
    assert upsell is not None
    assert upsell.upgrade_reasons[0] == "Also supports iOS (confirmed in the catalog)"


def test_losing_a_phone_platform_blocks_the_upsell():
    with_ios = product("with_ios", price=50.0, facts=[fact("google_home"), fact("ios")])
    matter = product("matter", price=70.0, facts=[fact("google_home"), fact("matter")])
    ranked = _ranked([with_ios, matter])
    assert ranking.upsell_rejection(_best(ranked, "matter"), _best(ranked, "with_ios"), None, 0.75) == (
        "loses_capability"
    )


def test_explicit_stand_alone_operation_is_an_upgrade_when_the_best_match_needs_a_hub():
    needs_hub = product(
        "hub", price=50.0, facts=[fact("google_home")], requirements=[requirement("philips_hue_bridge")]
    )
    standalone = product(
        "standalone",
        price=60.0,
        facts=[fact("google_home")],
        requirements=[requirement("philips_hue_bridge", alternatives=["philips_hue_bridge", "standalone"])],
    )
    ranked = _ranked([needs_hub, standalone])
    upsell = ranking.select_upsell(ranked, _best(ranked, "hub"), max_price=None, min_relative_relevance=0.75)
    assert upsell is not None
    assert upsell.product_id == "standalone"
    assert upsell.upgrade_reasons[0].startswith("Works without a separate hub (confirmed in the catalog)")
    assert "Philips Hue Bridge" in upsell.upgrade_reasons[0]


def test_a_product_without_a_hub_row_is_not_claimed_to_run_without_a_hub():
    needs_hub = product(
        "hub", price=50.0, facts=[fact("google_home")], requirements=[requirement("philips_hue_bridge")]
    )
    silent = product("silent", price=60.0, facts=[fact("google_home")])  # the catalog says nothing: unknown
    ranked = _ranked([needs_hub, silent])
    assert ranking.upsell_rejection(_best(ranked, "silent"), _best(ranked, "hub"), None, 0.75) == "no_advantage"


def test_a_product_that_uses_an_owned_hub_ranks_higher():
    hue = product("hue", facts=[fact("google_home")], requirements=[requirement("philips_hue_bridge")])
    bosch = product("bosch", facts=[fact("google_home")], requirements=[requirement("bosch_smart_home_controller")])
    scores: dict[str, float | None] = {"hue": 0.9, "bosch": 0.85}
    assert _ranked([hue, bosch], scores)[0].product.id == "hue"
    ranked = _ranked([hue, bosch], scores, owned_devices=["bosch_smart_home_controller"])
    assert ranked[0].product.id == "bosch"
    assert _best(ranked, "bosch").uses_owned_hub


def test_missing_hub_data_is_never_rewarded():
    needs_hub = product("hub", facts=[fact("google_home")], requirements=[requirement("philips_hue_bridge")])
    silent = product("silent", facts=[fact("google_home")])  # no hub row: unknown
    scores: dict[str, float | None] = {"hub": 0.9, "silent": 0.8}
    for owned in (None, []):
        ranked = _ranked([needs_hub, silent], scores, owned_devices=owned)
        assert ranked[0].product.id == "hub"
        assert {c.product.id: c.score for c in ranked} == {
            c.product.id: c.score for c in _ranked([needs_hub, silent], scores)
        }
