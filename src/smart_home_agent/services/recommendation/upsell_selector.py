from collections.abc import Sequence

from smart_home_agent.models import UpsellSuggestion
from smart_home_agent.services.recommendation.product_type import ProductType
from smart_home_agent.services.recommendation.ranking_candidate import RankingCandidate
from smart_home_agent.services.vocabulary import Vocabulary

# Upsell rules in evaluation order: a candidate rejected by a later rule got further (a closer near-miss).
UPSELL_RULES = (
    "no_price",
    "not_pricier",
    "over_budget",
    "other_product_type",
    "low_relevance",
    "loses_capability",
    "no_advantage",
)


class UpsellSelector:
    """At most one higher-priced alternative to the best match, only when it stays within the budget, loses no
    confirmed capability and has a verifiable advantage (an extra confirmed capability or phone platform, or
    explicit stand-alone operation where the best match needs a hub). Every upgrade reason is computed from
    structured data. Runs only on candidates that already passed the compatibility gate."""

    @classmethod
    def select(
        cls,
        ranked: Sequence[RankingCandidate],
        best: RankingCandidate,
        max_price: float | None,
        min_relative_relevance: float,
    ) -> UpsellSuggestion | None:
        """Higher-value alternative to `best`, chosen among compatible candidates only.

        Conditions (see `rejection`): same category and product type, higher price but within `max_price`,
        comparable relevance to the need, every confirmed capability of the best match, and at least one advantage:
        an extra confirmed capability or phone platform, or stand-alone operation where the best match needs a hub.
        """
        for candidate in ranked:  # already ordered by score: the best-fitting upgrade wins, not the priciest
            if not cls.rejection(candidate, best, max_price, min_relative_relevance):
                return cls._suggestion(candidate, best)
        return None

    @classmethod
    def rejection(
        cls, candidate: RankingCandidate, best: RankingCandidate, max_price: float | None, min_relative_relevance: float
    ) -> str | None:
        """Why `candidate` cannot be the upsell of `best` (None when it qualifies)."""
        price, base_price = candidate.product.price, best.product.price
        if candidate is best:
            return "best_match"
        if price is None or base_price is None:
            return "no_price"
        if price <= base_price:
            return "not_pricier"
        if max_price is not None and price > max_price:
            return "over_budget"
        if candidate.product.category != best.product.category or not ProductType.same(candidate.product, best.product):
            return "other_product_type"
        if candidate.relevance < min_relative_relevance * best.relevance:
            return "low_relevance"
        if not candidate.upgrade_capabilities >= best.upgrade_capabilities:
            return "loses_capability"
        if candidate.upgrade_capabilities == best.upgrade_capabilities and not cls.replaces_hub(candidate, best):
            return "no_advantage"
        return None

    @classmethod
    def blockers(
        cls,
        ranked: Sequence[RankingCandidate],
        best: RankingCandidate,
        max_price: float | None,
        min_relative_relevance: float,
    ) -> dict[str, int]:
        """Rejection reason -> number of candidates (the best match itself is not counted)."""
        counts: dict[str, int] = {}
        for candidate in ranked:
            reason = cls.rejection(candidate, best, max_price, min_relative_relevance)
            if reason and reason != "best_match":
                counts[reason] = counts.get(reason, 0) + 1
        return counts

    @staticmethod
    def replaces_hub(candidate: RankingCandidate, best: RankingCandidate) -> bool:
        """The best match needs a hub the customer may not own; the candidate explicitly runs without one."""
        return bool(best.needed_hubs) and not candidate.needed_hubs and candidate.product.runs_standalone

    @classmethod
    def _suggestion(cls, candidate: RankingCandidate, best: RankingCandidate) -> UpsellSuggestion:
        price, base_price = candidate.product.price or 0.0, best.product.price or 0.0
        extra_ids = sorted(candidate.upgrade_capabilities - best.upgrade_capabilities)
        extra = sorted(Vocabulary.label(c) for c in extra_ids)
        difference = round(price - base_price, 2)
        currency = candidate.product.currency or ""
        reasons = [f"Also supports {name} (confirmed in the catalog)" for name in extra]
        without_hub = cls.replaces_hub(candidate, best)
        if without_hub:
            hubs = ", ".join(sorted(Vocabulary.requirement_label(h) for h in best.needed_hubs))
            reasons.append(
                f"Works without a separate hub (confirmed in the catalog); {best.product.title} needs {hubs}"
            )
        reasons.append(f"Costs {difference:.2f} {currency} more than {best.product.title}".replace("  ", " "))
        return UpsellSuggestion(
            product_id=candidate.product.id,
            title=candidate.product.title,
            variant=candidate.product.variant,
            price=price,
            base_product_id=best.product.id,
            price_difference=difference,
            upgrade_reasons=reasons,
            extra_capabilities=extra_ids,
            replaces_hub=without_hub,
        )
