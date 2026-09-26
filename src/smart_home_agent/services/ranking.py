"""Business ranking and upselling. Runs only on candidates that already passed the compatibility gate.

The ranking is price-neutral: the best match is chosen on fit (semantic relevance, product-type
match, data completeness, confirmed capabilities), not on margin. Upselling then adds at most one
higher-priced alternative, only when it stays within the budget and offers strictly more
verifiable capabilities than the best match. Every upgrade reason is computed from structured data.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from smart_home_agent.models.product import Product
from smart_home_agent.models.recommendation import UpsellSuggestion
from smart_home_agent.services import vocabulary

WEIGHT_RELEVANCE = 0.6
WEIGHT_TYPE_MATCH = 0.15
WEIGHT_COMPLETENESS = 0.1
WEIGHT_CAPABILITIES = 0.15
CAPABILITY_SATURATION = 8  # this many confirmed capabilities give the full capability score

_WORD = re.compile(r"[\wäöüß]{4,}", re.IGNORECASE)


@dataclass(slots=True)
class RankingCandidate:
    product: Product
    relevance: float  # semantic similarity, normalized to the best candidate (0..1)
    type_match: bool
    capabilities: frozenset[str]  # confirmed canonical ecosystems, voice assistants and protocols
    score: float = 0.0


def _words(text: str | None) -> set[str]:
    return {w.casefold() for w in _WORD.findall(text or "")}


def type_matches(product: Product, need: str) -> bool:
    """The need names the product type (e.g. "thermostat" vs a "Heating valve adapter")."""
    need_words = _words(need)
    return bool(need_words & (_words(product.product_type) | _words(product.title)))


def same_product_type(a: Product, b: Product) -> bool:
    """Both products serve the same need: the words of the shorter product type are all contained in the
    longer one ("Radiator thermostat" ~ "Smart radiator thermostat", but not ~ "Room thermostat")."""
    words_a, words_b = _words(a.product_type), _words(b.product_type)
    if not words_a or not words_b:
        return False
    shorter, longer = sorted((words_a, words_b), key=len)
    return shorter <= longer


def build_candidates(
    products: Sequence[Product], raw_scores: dict[str, float | None], need: str
) -> list[RankingCandidate]:
    best = max((s for s in raw_scores.values() if s is not None), default=0.0)
    return [
        RankingCandidate(
            product=p,
            relevance=(raw_scores.get(p.id) or 0.0) / best if best > 0 else 0.0,
            type_match=type_matches(p, need),
            capabilities=frozenset(p.supported_values()),
        )
        for p in products
    ]


def score(candidate: RankingCandidate) -> float:
    capability_score = min(1.0, len(candidate.capabilities) / CAPABILITY_SATURATION)
    return (
        WEIGHT_RELEVANCE * candidate.relevance
        + WEIGHT_TYPE_MATCH * float(candidate.type_match)
        + WEIGHT_COMPLETENESS * candidate.product.completeness_score
        + WEIGHT_CAPABILITIES * capability_score
    )


def rank(candidates: Sequence[RankingCandidate]) -> list[RankingCandidate]:
    for candidate in candidates:
        candidate.score = round(score(candidate), 4)
    return sorted(candidates, key=lambda c: (-c.score, c.product.id))


def select_upsell(
    ranked: Sequence[RankingCandidate],
    best: RankingCandidate,
    max_price: float | None,
    min_relative_relevance: float,
) -> UpsellSuggestion | None:
    """Higher-value alternative to `best`, chosen among compatible candidates only.

    Conditions: same category and product type, higher price but within `max_price`, comparable relevance to the
    need, and a strict superset of the best match's confirmed capabilities.
    """
    base_price = best.product.price
    if base_price is None:
        return None
    for candidate in ranked:  # already ordered by score: the best-fitting upgrade wins, not the priciest
        price = candidate.product.price
        if (
            candidate is best
            or price is None
            or price <= base_price
            or (max_price is not None and price > max_price)
            or candidate.product.category != best.product.category
            or not same_product_type(candidate.product, best.product)
            or candidate.relevance < min_relative_relevance * best.relevance
            or not candidate.capabilities > best.capabilities
        ):
            continue
        extra = sorted(vocabulary.label(c) for c in candidate.capabilities - best.capabilities)
        difference = round(price - base_price, 2)
        currency = candidate.product.currency or ""
        reasons = [f"Also supports {name} (confirmed in the catalog)" for name in extra]
        reasons.append(f"Costs {difference:.2f} {currency} more than {best.product.title}".replace("  ", " "))
        return UpsellSuggestion(
            product_id=candidate.product.id,
            title=candidate.product.title,
            price=price,
            base_product_id=best.product.id,
            price_difference=difference,
            upgrade_reasons=reasons,
        )
    return None
