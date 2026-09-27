from evals.variant import evaluate, guard_failures, report
from smart_home_agent.models.recommendation import RecommendationRequest
from tests.fakes import fact, product, services_for

PRODUCTS = [
    product("white", title="Thermostat X", price=55.0, subtitle="Weiß", facts=[fact("google_home")]),
    product("anthracite", title="Thermostat X", price=55.0, subtitle="Anthrazit", facts=[fact("google_home")]),
    product("other", title="Thermostat Y", price=60.0, facts=[fact("google_home"), fact("matter")]),
]
REQUEST = RecommendationRequest(need="thermostat", category="heating_control", must_support=["google_home"])


def _recommend(request):
    return services_for(PRODUCTS, {"white": 0.9, "anthracite": 0.85, "other": 0.8}).recommendation.recommend(request)


def test_grouped_result_passes_the_guards_and_counts_versions():
    [result] = evaluate(_recommend, [REQUEST])
    assert (result.listed, result.with_versions) == (2, 1)
    assert result.version_statuses == {"confirmed": 1}
    assert result.guard_failures == []
    assert "entries with other versions: 1" in report([result])


def test_guards_catch_a_product_listed_twice():
    result = _recommend(REQUEST)
    twice = result.model_copy(update={"unconfirmed": [result.confirmed[0]]})
    assert "product_listed_twice" in guard_failures(twice)
    assert "confirmed_and_unconfirmed_versions" in guard_failures(twice)


def test_guards_catch_a_version_without_any_distinguishing_text():
    result = _recommend(REQUEST)
    entry = result.confirmed[0]
    anonymous = entry.model_copy(update={"product": entry.product.model_copy(update={"subtitle": None})})
    assert guard_failures(result.model_copy(update={"confirmed": [anonymous]})) == ["version_not_distinguishable"]
