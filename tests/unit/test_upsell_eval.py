from smart_home_agent.models.recommendation import RecommendationRequest
from smart_home_agent.upsell_eval import binding_rule, evaluate, guard_failures, report
from tests.fakes import fact, product, requirement, services_for

PRODUCTS = [
    product("cheap", price=55.0, facts=[fact("google_home"), fact("wifi")]),
    product("premium", price=120.0, facts=[fact("google_home"), fact("wifi"), fact("matter")]),
]
REQUEST = RecommendationRequest(need="radiator thermostat", category="heating_control", must_support=["google_home"])


def _recommend(request):
    return services_for(PRODUCTS, {"cheap": 0.9, "premium": 0.85}).recommendation.recommend(request)


def test_valid_upsell_passes_every_guard_and_counts_in_the_report():
    results = evaluate(_recommend, [REQUEST])
    assert results[0].upsell == "premium"
    assert results[0].guard_failures == []
    text = report(results)
    assert "upsell offer rate: 1/1 (100%)" in text
    assert "all 0" in text


def test_guards_catch_an_upsell_over_budget():
    result = _recommend(REQUEST).model_copy(update={"request": REQUEST.model_copy(update={"max_price": 100})})
    assert "upsell_over_budget" in guard_failures(result)


def test_binding_rule_is_the_furthest_rule_reached():
    assert binding_rule({"not_pricier": 3, "no_advantage": 1}) == "no_advantage"
    assert binding_rule({"loses_capability": 2, "no_advantage": 1}) == "no_advantage"
    assert binding_rule({}) == "no_other_confirmed_candidate"
    # Versions of the best match are set aside before any rule, so every real rule outranks them.
    assert binding_rule({"other_version_of_best": 2, "not_pricier": 1}) == "not_pricier"
    assert binding_rule({"other_version_of_best": 2}) == "other_version_of_best"


def test_guards_catch_an_upsell_without_an_advantage_reason():
    result = _recommend(REQUEST)
    assert result.upsell is not None
    assert result.upsell.extra_capabilities or result.upsell.replaces_hub
    price_only = result.upsell.model_copy(update={"extra_capabilities": [], "replaces_hub": False})
    assert "upsell_without_advantage_reason" in guard_failures(result.model_copy(update={"upsell": price_only}))
    # The guard reads the data, not the wording: rewording the reasons does not satisfy it.
    reworded = price_only.model_copy(update={"upgrade_reasons": ["Premium build quality"]})
    assert "upsell_without_advantage_reason" in guard_failures(result.model_copy(update={"upsell": reworded}))


def test_uplift_does_not_add_up_alternatives():
    from smart_home_agent.upsell_eval import CaseResult

    def case(upsell: str | None, delta: float, hubs: float) -> CaseResult:
        return CaseResult(
            need="n",
            best_match="b",
            best_price=100.0,
            upsell=upsell,
            upsell_delta=delta,
            accessories=[],
            accessories_total=hubs,
            blockers={},
            guard_failures=[],
        )

    # The upsell works without the hub the best match needs: upsell (+30) or best + hub (+50), not +80.
    assert case("u", 30.0, 50.0).uplift == 0.5
    assert case(None, 0.0, 20.0).uplift == 0.2


def test_report_counts_best_matches_that_need_a_hub_the_customer_lacks():
    hub = product("hub", price=40.0, facts=[fact("google_home")], requirements=[requirement("philips_hue_bridge")])

    def recommend(request):
        return services_for([hub], {"hub": 0.9}).recommendation.recommend(request)

    stated = REQUEST.model_copy(update={"owned_devices": []})
    results = evaluate(recommend, [REQUEST, stated])
    assert [r.best_missing_hub for r in results] == [False, True]
    assert "best match needs a hub the customer lacks (ownership stated): 1/1 (100%)" in report(results)
