from smart_home_agent.models.recommendation import RecommendationRequest
from smart_home_agent.upsell_eval import binding_rule, evaluate, guard_failures, report
from tests.fakes import fact, product, services_for

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
    assert binding_rule({"not_pricier": 3, "not_capability_superset": 1}) == "not_capability_superset"
    assert binding_rule({}) == "no_other_confirmed_candidate"
    # Versions of the best match are set aside before any rule, so every real rule outranks them.
    assert binding_rule({"other_version_of_best": 2, "not_pricier": 1}) == "not_pricier"
    assert binding_rule({"other_version_of_best": 2}) == "other_version_of_best"
