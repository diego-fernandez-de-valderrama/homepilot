# Upselling in HomePilot

The business KPI says the assistant should prioritise product upselling. HomePilot does this in code, not in the prompt, and only in ways the catalog data can back up. This document explains the mechanism, the rules that keep it honest and how the KPI is measured.

## Principles

- **Trust first.** The best match is chosen on fit to the need. Price is not part of its score.
- **Compatibility gates everything.** An upsell or accessory is only offered for `confirmed` products, meaning every requested ecosystem, voice assistant or protocol is `supported` in the catalog. Unknown stays unknown and is never upsold.
- **Every argument comes from data.** Upgrade reasons and bundle totals are computed from PostgreSQL. The model may only repeat them.
- **The budget is a hard limit for upsells.** A required hub may push a bundle over the budget; the agent then says so openly.
- **Cheaper valid options are never hidden.** All confirmed alternatives stay in the result.

## Where it runs

Everything happens inside the `recommend_products` tool (`tools/recommend.py`), in the pipeline of `services/recommendation.py`:

```
need + constraints (category, budget, brands, must_support, owned hubs)
  -> candidates (Qdrant semantic top-K + PostgreSQL structured matches)
  -> hydrate from PostgreSQL
  -> hard filters (category, price, brand)
  -> compatibility gate: confirmed | unconfirmed | excluded
  -> price-neutral ranking               (services/ranking.py)
  -> upsell: at most one upgrade         (ranking.select_upsell)
  -> accessories: required hubs          (services/accessories.py)
  -> the agent writes the answer from this result
```

The tool result contains `best_match`, `upsell` and `accessories`. The session stores the upsell as `last_upsell` and adds accessory ids to `candidate_products`, so follow-up questions and the output check know these products.

## Lever 1: the upgrade (upsell)

`ranking.select_upsell` walks the confirmed candidates in ranking order and returns the first one that passes every rule. So the best-fitting upgrade wins, not the most expensive one. The rules are evaluated in this order (`ranking.UPSELL_RULES`, `ranking.upsell_rejection`):

| Rule | Rejection reason |
|---|---|
| Both products have a price | `no_price` |
| The upgrade costs more than the best match | `not_pricier` |
| The upgrade stays within `max_price` | `over_budget` |
| Same category and same product type ("Radiator thermostat" ~ "Smart radiator thermostat", not ~ "Room thermostat") | `other_product_type` |
| Relevance at least `AGENT_UPSELL_MIN_RELEVANCE` (default 0.75) x the best match's relevance | `low_relevance` |
| Confirmed capabilities (ecosystems, voice assistants, protocols) are a strict superset of the best match's | `not_capability_superset` |

One extra rule is applied in `services/recommendation.py` before `select_upsell`: the upgrade must not need a hub or gateway that the best match does not need (reported as `needs_extra_hub`). Otherwise its price difference would understate what the customer really pays.

The `UpsellSuggestion` carries `upgrade_reasons` computed from data, for example:

- "Also supports Matter (confirmed in the catalog)"
- "Costs 40.00 EUR more than Product X"

## Lever 2: required hubs (cross-sell)

Many devices only work with a hub that is itself in the catalog: the Homematic IP Access Point, the Bosch Smart Home Controller, the Philips Hue Bridge, the Gardena gateway, and others. `services/accessories.py` turns that requirement into an offer:

1. The compatibility check (`services/compatibility.check_requirement`) marks each required hub or gateway of a product:
   - `satisfied` when the customer owns it or the product can run stand-alone;
   - `missing` when the customer listed their devices and it is not among them;
   - `unverified` when the customer has not said what they own.
2. For `missing` and `unverified` requirements of the best match and of the upgrade, `AccessoryService` looks up a hub product:
   - only products in the `hub_gateway` category (loaded once and cached);
   - the title must contain every keyword mapped to the canonical requirement id in `HUB_TITLE_KEYWORDS` (for example `philips_hue_bridge` -> "hue", "bridge");
   - starter sets are never offered, only the bare hub;
   - the cheapest match wins (ties broken by id).
3. Requirements without a safe mapping, such as the generic `smart_hub`, get no suggestion.

Each `AccessorySuggestion` contains the product it belongs to, the requirement, its status, the hub product and the `bundle_total` (product + hub).

## How the agent presents it

The rules live in `agent/prompts.py`, section "Recommendations and upselling":

- Lead with the best match. Present the upgrade after it, using only its `upgrade_reasons` and the price difference, and show it with `<upgrade from="ID" to="ID"/>`.
- Name a required hub with `<item id="ID"/>`, say it is required ("required unless you already own one" when `unverified`) and give the bundle total. If the bundle exceeds the budget, say so.
- Never recommend an incompatible or over-budget product because it is more expensive.

The `<upgrade>` block only renders for the pair stored in `last_upsell` (`services/rich_content.py`). The output check rejects product ids that did not come from a tool result.

## Measuring the KPI

`uv run python -m smart_home_agent upsell-eval` (`upsell_eval.py`) runs 25 fixed EN/DE requests through the real pipeline. It makes one embedding call per request and no chat model call. It reports:

| Metric | Definition |
|---|---|
| Upsell offer rate | share of recommendations with an `upsell` |
| Attach rate | share offering at least one required hub |
| Basket uplift | (best match + upsell difference + hubs of the best match) / best match - 1, mean and median |
| Binding rule | when no upsell fired: the furthest rule a near-miss candidate reached, i.e. the rule to revisit |
| Guard metrics (must be 0) | upsell over budget, not confirmed, not pricier, without a capability reason; hub attached to another product |

The command exits with code 1 if a guard metric is not 0. The rejection counts behind the binding rule are kept in `Recommendation.upsell_blockers`, which is excluded from the tool output, so the model never sees them.

In production, every `recommend_products` call logs one line:

```
commerce best_match=... upsell=... upsell_delta=... accessories=[...] bundle_totals=[...]
```

The same KPIs can be computed from these lines.

## Current numbers and next steps

First measurement on the 25 cases:

- upsell offer rate: 0%;
- attach rate: 36%;
- basket uplift: mean 46%, median 0% (all from hubs);
- guard metrics: all 0.

The binding rule is `not_capability_superset` in 20 of 25 cases: the catalog rarely has a pricier product of the same type that supports everything the best match supports plus more. Possible next steps, each measurable with `upsell-eval`:

- count more verifiable differences as upgrade reasons: control options, mobile OS, "no hub needed", fewer required subscriptions;
- let hubs the customer already owns influence the ranking, so a product that fits the existing setup comes first.

## Files

| File | Role |
|---|---|
| `services/ranking.py` | price-neutral ranking, upsell rules, `select_upsell`, `upsell_blockers` |
| `services/recommendation.py` | pipeline, extra-hub filter, attaches accessories |
| `services/accessories.py` | hub lookup and `AccessorySuggestion` |
| `models/recommendation.py` | `UpsellSuggestion`, `AccessorySuggestion`, `Recommendation` |
| `tools/recommend.py` | tool, session state, commerce log line |
| `agent/prompts.py` | presentation rules |
| `upsell_eval.py` | KPI evaluation cases and report |
| `tests/unit/test_ranking.py`, `test_recommendation.py`, `test_accessories.py`, `test_upsell_eval.py` | unit tests |
