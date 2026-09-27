from collections.abc import Mapping, Sequence

from smart_home_agent.models import UPGRADE_DIMENSIONS, CompatibilityResult, Product
from smart_home_agent.services.recommendation.product_type import ProductType
from smart_home_agent.services.recommendation.ranking_candidate import RankingCandidate


class Ranker:
    """Price-neutral ranking: the best match is chosen on fit (semantic relevance, product-type match, data
    completeness, confirmed capabilities, and whether the catalog says it works with a hub the customer owns),
    not on margin. Compatibility is already decided; the ranking only reads its flags."""

    WEIGHT_RELEVANCE = 0.6
    WEIGHT_TYPE_MATCH = 0.15
    WEIGHT_COMPLETENESS = 0.1
    WEIGHT_CAPABILITIES = 0.15
    # Added when the catalog names a hub for the product that the customer owns. A bonus for explicit fit, not a
    # penalty for a missing hub: that would reward products whose hub requirement is simply not in the catalog.
    WEIGHT_OWNED_HUB = 0.1
    CAPABILITY_SATURATION = 8  # this many confirmed capabilities give the full capability score

    @staticmethod
    def build_candidates(
        products: Sequence[Product],
        raw_scores: dict[str, float | None],
        need: str,
        results: Mapping[str, CompatibilityResult] | None = None,
    ) -> list[RankingCandidate]:
        """`results`: the compatibility check per product id, which gives the hub fields."""
        best = max((s for s in raw_scores.values() if s is not None), default=0.0)
        results = results or {}
        return [
            RankingCandidate(
                product=p,
                relevance=(raw_scores.get(p.id) or 0.0) / best if best > 0 else 0.0,
                type_match=ProductType.matches_need(p, need),
                capabilities=frozenset(p.supported_values()),
                upgrade_capabilities=frozenset(p.supported_values(UPGRADE_DIMENSIONS)),
                needed_hubs=result.needed_hubs() if (result := results.get(p.id)) else frozenset(),
                uses_owned_hub=bool(result and result.uses_owned_hub),
            )
            for p in products
        ]

    @classmethod
    def rank(cls, candidates: Sequence[RankingCandidate]) -> list[RankingCandidate]:
        """Sets each candidate's score and returns them best first (ties by product id)."""
        for candidate in candidates:
            candidate.score = round(cls.score(candidate), 4)
        return sorted(candidates, key=lambda c: (-c.score, c.product.id))

    @classmethod
    def score(cls, candidate: RankingCandidate) -> float:
        capability_score = min(1.0, len(candidate.capabilities) / cls.CAPABILITY_SATURATION)
        return (
            cls.WEIGHT_RELEVANCE * candidate.relevance
            + cls.WEIGHT_TYPE_MATCH * float(candidate.type_match)
            + cls.WEIGHT_COMPLETENESS * candidate.product.completeness_score
            + cls.WEIGHT_CAPABILITIES * capability_score
            + cls.WEIGHT_OWNED_HUB * float(candidate.uses_owned_hub)
        )
