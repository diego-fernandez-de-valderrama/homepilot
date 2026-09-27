"""Product version evaluation: how recommendations handle products sold in several versions (measurement only).

uv run python -m evals variant

Versions of one product (another color, size, pack or brightness) share the catalog title. Runs the real
recommendation pipeline (one query embedding per case, no chat model) over the upselling cases plus cases
for version-heavy product lines, and reports:
- listed entries, and how many carry `other_versions` (with the status mix of those versions);
- guard metrics, which must stay 0: two entries of one product (a duplicate title, also across confirmed and
  unconfirmed), an upsell that is a version of the best match, or an entry with other versions but nothing
  that tells it apart (no variant, no subtitle). The command exits with 1 if any guard fails.
"""

from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel

from evals.upsell import CASES as UPSELL_CASES
from smart_home_agent.models.recommendation import Recommendation, RecommendationRequest


def _case(need: str, category: str, **fields: object) -> RecommendationRequest:
    return RecommendationRequest.model_validate({"need": need, "category": category, **fields})


VERSION_CASES: tuple[RecommendationRequest, ...] = (
    _case("Paulmann smarte LED-Lampe", "smart_bulb", brands=["Paulmann"]),
    _case("Homematic IP access point to control my devices", "hub_gateway", brands=["Homematic IP"]),
    _case("Innr GU10 smart spot for Alexa", "smart_bulb", brands=["Innr"], max_price=60, must_support=["amazon_alexa"]),
    _case("Philips Hue outdoor LED strip", "led_strip", brands=["Philips Hue"], max_price=200),
    _case("Philips Hue Tento panel for Alexa", "led_panel", brands=["Philips Hue"], must_support=["amazon_alexa"]),
    _case("smartes LED-Panel mit WLAN", "led_panel", brands=["Ledvance"]),
    _case("Eglo connect.z smart bulb", "smart_bulb", brands=["Eglo"]),
    _case("Ring outdoor camera with spotlight", "security_camera", brands=["Ring"]),
)  # "window contact sensor" and "Türschloss mit App" are already in UPSELL_CASES: never counted twice
CASES: tuple[RecommendationRequest, ...] = (*UPSELL_CASES, *VERSION_CASES)


class CaseResult(BaseModel):
    need: str
    listed: int
    with_versions: int
    version_statuses: dict[str, int]
    guard_failures: list[str]


def guard_failures(result: Recommendation) -> list[str]:
    """Invariants of the version grouping (all computable from the result alone)."""
    failures = []
    entries = [*result.confirmed, *result.unconfirmed]
    titles = [r.product.title for r in entries]
    if len(titles) != len(set(titles)):
        failures.append("product_listed_twice")
    if {r.product.title for r in result.confirmed} & {r.product.title for r in result.unconfirmed}:
        failures.append("confirmed_and_unconfirmed_versions")
    best = next((r for r in result.confirmed if r.product.id == result.best_match), None)
    if result.upsell and best and result.upsell.title == best.product.title:
        failures.append("upsell_is_a_version_of_best")
    if any(r.other_versions and not (r.product.variant or r.product.subtitle) for r in entries):
        failures.append("version_not_distinguishable")
    return failures


def case_result(result: Recommendation) -> CaseResult:
    entries = [*result.confirmed, *result.unconfirmed]
    return CaseResult(
        need=result.request.need,
        listed=len(entries),
        with_versions=sum(1 for r in entries if r.other_versions),
        version_statuses=dict(Counter(v.status for r in entries for v in r.other_versions)),
        guard_failures=guard_failures(result),
    )


def report(results: Sequence[CaseResult]) -> str:
    listed = sum(r.listed for r in results)
    with_versions = sum(r.with_versions for r in results)
    statuses: Counter[str] = Counter()
    for r in results:
        statuses.update(r.version_statuses)
    guards = Counter(failure for r in results for failure in r.guard_failures)
    lines = [
        f"cases: {len(results)}",
        f"listed entries: {listed}",
        f"entries with other versions: {with_versions}",
        "other versions by status for the request:",
    ]
    lines += [f"  {status}: {count}" for status, count in statuses.most_common()] or ["  none"]
    lines += ["", "per case (entries / with versions):"]
    lines += [f"  {r.listed:>2} / {r.with_versions:<2} {r.need}" for r in results]
    lines += ["", "guard metrics (must be 0):"]
    lines += [f"  {failure}: {count}" for failure, count in guards.items()] or ["  all 0"]
    return "\n".join(lines)


def evaluate(recommend, cases: Sequence[RecommendationRequest] = CASES) -> list[CaseResult]:
    """`recommend`: RecommendationService.recommend (or a stand-in in tests)."""
    return [case_result(recommend(case)) for case in cases]
