"""Upselling KPI evaluation over a fixed set of recommendation requests (measurement only).

uv run python -m evals upsell

Runs the real recommendation pipeline (one query embedding per case, no chat model) and reports:
- upsell offer rate: share of recommendations (with a best match) that carry an upsell;
- attach rate: share that offer at least one required hub/gateway from the catalog;
- basket uplift: (best match + upsell delta + accessories) / best match - 1, mean and median;
- no-upsell diagnostics: the binding rule per case, i.e. the furthest rule that a near-miss candidate reached;
- setup fit: in the cases where the customer said what they own, how often the best match still needs a hub
  they do not have;
- guard metrics, which must stay 0: upsell over budget, not confirmed, not pricier, without an advantage
  reason, or accessories attached to another product. The command exits with 1 if any guard fails.
"""

import statistics
from collections import Counter
from collections.abc import Sequence

from catalog_ingestion.domain.enums import FactStatus
from pydantic import BaseModel

from smart_home_agent.models.recommendation import Recommendation, RecommendationRequest
from smart_home_agent.services.ranking import UPSELL_RULES

# The hub filter runs after every ranking rule; versions of the best match are set aside before any rule.
_FUNNEL = ("other_version_of_best", *UPSELL_RULES, "needs_extra_hub")


def _case(need: str, category: str, **fields: object) -> RecommendationRequest:
    return RecommendationRequest.model_validate({"need": need, "category": category, **fields})


CASES: tuple[RecommendationRequest, ...] = (
    _case("Heizkörperthermostat", "heating_control"),
    _case("smart radiator thermostat for Google Home", "heating_control", must_support=["google_home"]),
    _case("Thermostat für Alexa unter 80 Euro", "heating_control", max_price=80, must_support=["amazon_alexa"]),
    _case("radiator thermostat Homematic IP", "heating_control", brands=["Homematic IP"]),
    _case(
        "radiator thermostat, I already have an access point",
        "heating_control",
        owned_devices=["homematic_ip_access_point"],
    ),
    _case("smart bulb E27 colour", "smart_bulb"),
    _case("LED Leuchtmittel für Apple Home", "smart_bulb", must_support=["apple_home"]),
    _case("Zigbee bulb under 20 EUR", "smart_bulb", max_price=20, must_support=["zigbee"]),
    _case("Philips Hue Lampe", "smart_bulb", brands=["Philips Hue"], owned_devices=[]),
    _case("smart plug with energy monitoring", "smart_plug"),
    _case("WLAN Steckdose für Alexa", "smart_plug", must_support=["amazon_alexa", "wifi"]),
    _case("Matter smart plug", "smart_plug", must_support=["matter"]),
    _case("outdoor security camera", "security_camera"),
    _case("Überwachungskamera für Google Home bis 150 Euro", "security_camera", max_price=150),
    _case("smart door lock", "door_lock"),
    _case("Türschloss mit App", "door_lock", max_price=200),
    _case("roller shutter control for Alexa", "shutter_blind_control", must_support=["amazon_alexa"]),
    _case("Rollladensteuerung", "shutter_blind_control"),
    _case("alarm system for my flat", "alarm_system"),
    _case("Alarmanlage Set bis 150 Euro", "alarm_system", max_price=150),
    _case("wall switch for lights", "switch"),
    _case("Unterputz Schalter Homematic IP", "switch", brands=["Homematic IP"], owned_devices=[]),
    _case("window contact sensor", "contact_sensor"),
    _case("smoke detector smart", "safety_detector"),
    _case("video doorbell", "doorbell_intercom"),
    # Stated ownership: the ranking should prefer products that fit the customer's hub.
    _case("smart bulb, I have a Hue Bridge", "smart_bulb", owned_devices=["philips_hue_bridge"]),
    _case(
        "Heizkörperthermostat, ich habe den Bosch Controller",
        "heating_control",
        owned_devices=["bosch_smart_home_controller"],
    ),
    _case(
        "window contact, I have a Homematic IP access point",
        "contact_sensor",
        owned_devices=["homematic_ip_access_point"],
    ),
    _case("Lichtschalter, ich habe keine Zentrale", "switch", owned_devices=[]),
)


class CaseResult(BaseModel):
    need: str
    best_match: str | None
    best_price: float | None
    upsell: str | None
    upsell_delta: float
    accessories: list[str]
    accessories_total: float  # hubs offered for the best match
    upsell_accessories_total: float = 0.0  # hubs offered for the upsell
    blockers: dict[str, int]
    guard_failures: list[str]
    ownership_stated: bool = False
    best_missing_hub: bool = False  # the best match needs a hub the customer said they do not own

    @property
    def uplift(self) -> float | None:
        """Largest basket increase the offer allows over the best match alone. The customer takes the upsell (with
        its own hubs) or the best match with its hubs: these are alternatives, never added up (an upsell that
        works without a hub replaces that hub)."""
        if not self.best_price:
            return None
        upsell_path = self.upsell_delta + self.upsell_accessories_total if self.upsell else 0.0
        return max(upsell_path, self.accessories_total) / self.best_price


def guard_failures(result: Recommendation) -> list[str]:
    """Invariants the upselling must never break (all computable from the result alone)."""
    failures: list[str] = []
    upsell = result.upsell
    confirmed = {r.product.id: r for r in result.confirmed}
    if upsell:
        best = confirmed.get(result.best_match or "")
        max_price = result.request.max_price
        if max_price is not None and upsell.price > max_price:
            failures.append("upsell_over_budget")
        target = confirmed.get(upsell.product_id)
        if target is None or target.compatibility is not FactStatus.SUPPORTED:
            failures.append("upsell_not_confirmed")
        if best is None or best.product.price is None or upsell.price <= best.product.price:
            failures.append("upsell_not_pricier")
        if not upsell.extra_capabilities and not upsell.replaces_hub:  # from data, not from the reason wording
            failures.append("upsell_without_advantage_reason")
    offered = {result.best_match, upsell and upsell.product_id}
    if any(a.for_product_id not in offered for a in result.accessories):
        failures.append("accessory_for_other_product")
    return failures


def case_result(result: Recommendation) -> CaseResult:
    best = next((r for r in result.confirmed if r.product.id == result.best_match), None)
    best_accessories = [a for a in result.accessories if a.for_product_id == result.best_match]
    upsell_id = result.upsell.product_id if result.upsell else None
    upsell_accessories = [a for a in result.accessories if upsell_id and a.for_product_id == upsell_id]
    return CaseResult(
        need=result.request.need,
        best_match=result.best_match,
        best_price=best.product.price if best else None,
        upsell=result.upsell.product_id if result.upsell else None,
        upsell_delta=result.upsell.price_difference if result.upsell else 0.0,
        accessories=[a.product_id for a in result.accessories],
        accessories_total=sum(a.price for a in best_accessories),
        upsell_accessories_total=sum(a.price for a in upsell_accessories),
        blockers=result.upsell_blockers,
        guard_failures=guard_failures(result),
        ownership_stated=result.request.owned_devices is not None,
        best_missing_hub=bool(best and best.missing_requirements),
    )


def binding_rule(blockers: dict[str, int]) -> str:
    """The last rule in the funnel that rejected a candidate: loosening it is what could produce an upsell."""
    return max(blockers, key=_FUNNEL.index, default="no_other_confirmed_candidate")


def _pct(part: int, whole: int) -> str:
    return f"{part}/{whole} ({part / whole:.0%})" if whole else "0/0"


def report(results: Sequence[CaseResult]) -> str:
    with_best = [r for r in results if r.best_match]
    uplifts = [u for r in with_best if (u := r.uplift) is not None]
    binding = Counter(binding_rule(r.blockers) for r in with_best if not r.upsell)
    guards = Counter(failure for r in results for failure in r.guard_failures)
    stated = [r for r in with_best if r.ownership_stated]
    lines = [
        f"cases: {len(results)}, with a best match: {len(with_best)}",
        f"upsell offer rate: {_pct(sum(1 for r in with_best if r.upsell), len(with_best))}",
        f"attach rate (required hub offered): {_pct(sum(1 for r in with_best if r.accessories), len(with_best))}",
        "basket uplift: "
        + (f"mean {statistics.mean(uplifts):.1%}, median {statistics.median(uplifts):.1%}" if uplifts else "n/a"),
        "best match needs a hub the customer lacks (ownership stated): "
        + _pct(sum(1 for r in stated if r.best_missing_hub), len(stated)),
        "",
        "per case:",
    ]
    for r in results:
        lines.append(
            f"  {r.need[:45]:45} best={r.best_match or '-':8} upsell={r.upsell or '-':8} "
            f"(+{r.upsell_delta:.2f}) hubs={','.join(r.accessories) or '-'}"
        )
    lines += ["", "binding rule when no upsell fired (cases):"]
    lines += [f"  {rule}: {count}" for rule, count in binding.most_common()] or ["  none"]
    lines += ["", "guard metrics (must be 0):"]
    lines += [f"  {failure}: {count}" for failure, count in guards.items()] or ["  all 0"]
    return "\n".join(lines)


def evaluate(recommend, cases: Sequence[RecommendationRequest] = CASES) -> list[CaseResult]:
    """`recommend`: RecommendationService.recommend (or a stand-in in tests)."""
    return [case_result(recommend(case)) for case in cases]
