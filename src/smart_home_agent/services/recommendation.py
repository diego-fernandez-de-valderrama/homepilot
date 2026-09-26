"""Recommendation pipeline, enforced in code:

requirements -> candidates (semantic + structured) -> hard filters -> compatibility gate
-> ranking -> upselling.

Only `confirmed` products (every requested term supported) can be the best match or the upsell.
An upsell must not need a hub that the best match does not need (its price difference would understate the
real extra cost). Required hubs the customer may not own are offered as accessories, from the catalog.
`unconfirmed` products (some term unknown) are returned separately so the agent can mention them
honestly; `unsupported` products are excluded.
"""

from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models.compatibility import CompatibilityResult
from smart_home_agent.models.recommendation import (
    AccessorySuggestion,
    RankedProduct,
    Recommendation,
    RecommendationRequest,
    UpsellSuggestion,
)
from smart_home_agent.models.search import ProductFilter
from smart_home_agent.services import compatibility, ranking, vocabulary
from smart_home_agent.services.accessories import AccessoryService
from smart_home_agent.services.filtering import rejection_reason
from smart_home_agent.services.ranking import RankingCandidate
from smart_home_agent.services.retrieval import RetrievalService


def _needed_hubs(result: CompatibilityResult) -> frozenset[str]:
    """Required hubs/gateways the customer does not (or did not say they) own."""
    return frozenset(r.canonical_item or r.label for r in result.requirements if r.status in ("missing", "unverified"))


def _ranked(candidate: RankingCandidate, result: CompatibilityResult) -> RankedProduct:
    return RankedProduct(
        product=candidate.product.summary(),
        compatibility=result.overall,
        checks=result.checks,
        relevance=round(candidate.relevance, 4),
        score=candidate.score,
        capabilities=sorted(vocabulary.label(c) for c in candidate.capabilities),
        missing_requirements=[r.label for r in result.requirements if r.status == "missing"],
        unverified_requirements=[r.label for r in result.requirements if r.status == "unverified"],
        requires_professional_installation=result.requires_professional_installation,
    )


class RecommendationService:
    def __init__(
        self,
        retrieval: RetrievalService,
        accessories: AccessoryService,
        candidate_pool: int,
        upsell_min_relevance: float,
    ) -> None:
        self._retrieval = retrieval
        self._accessories = accessories
        self._pool = candidate_pool
        self._upsell_min_relevance = upsell_min_relevance

    def _upsell(
        self,
        best: RankingCandidate,
        confirmed: list[RankingCandidate],
        results: dict[str, CompatibilityResult],
        request: RecommendationRequest,
    ) -> tuple[UpsellSuggestion | None, list[AccessorySuggestion], dict[str, int]]:
        """(upsell, required-hub accessories for the best match and the upsell, why no upsell fired)."""
        best_hubs = _needed_hubs(results[best.product.id])
        eligible = [c for c in confirmed if _needed_hubs(results[c.product.id]) <= best_hubs]
        upsell = ranking.select_upsell(eligible, best, request.max_price, self._upsell_min_relevance)
        blockers: dict[str, int] = {}
        if not upsell:
            blockers = ranking.upsell_blockers(confirmed, best, request.max_price, self._upsell_min_relevance)
            # Candidates that pass every ranking rule can only have been dropped by the extra-hub filter.
            needs_hub = sum(
                1
                for c in confirmed
                if c is not best
                and not ranking.upsell_rejection(c, best, request.max_price, self._upsell_min_relevance)
            )
            if needs_hub:
                blockers["needs_extra_hub"] = needs_hub
        offered = [best, *(c for c in confirmed if upsell and c.product.id == upsell.product_id)]
        accessories = [
            accessory
            for c in offered
            for accessory in self._accessories.for_product(c.product, results[c.product.id].requirements)
        ]
        return upsell, accessories, blockers

    def recommend(self, request: RecommendationRequest) -> Recommendation:
        terms = [vocabulary.term(canonical) for canonical in request.must_support]
        criteria = ProductFilter(
            category=request.category,
            min_price=request.min_price,
            max_price=request.max_price,
            brands=request.brands,
            supports=request.must_support,
        )
        products, scores = self._retrieval.candidates(request.need, criteria, self._pool)

        excluded: dict[str, int] = {}
        passed = []
        for product in products:
            reason = rejection_reason(product, criteria)
            if reason:
                excluded[reason] = excluded.get(reason, 0) + 1
            else:
                passed.append(product)

        results = {p.id: compatibility.evaluate(p, terms, request.owned_devices) for p in passed}
        candidates = ranking.rank(ranking.build_candidates(passed, scores, request.need))
        confirmed = [c for c in candidates if results[c.product.id].overall is FactStatus.SUPPORTED]
        unconfirmed = [c for c in candidates if results[c.product.id].overall is FactStatus.UNKNOWN]
        unsupported = len(candidates) - len(confirmed) - len(unconfirmed)
        if unsupported:
            excluded["unsupported"] = unsupported

        best = confirmed[0] if confirmed else None
        upsell, accessories, blockers = self._upsell(best, confirmed, results, request) if best else (None, [], {})
        shown = confirmed[: request.limit]
        if upsell and upsell.product_id not in {c.product.id for c in shown}:
            shown.append(next(c for c in confirmed if c.product.id == upsell.product_id))

        notes: list[str] = []
        if not confirmed:
            notes.append("No candidate is confirmed for every requirement; do not present any product as compatible.")
        if unconfirmed:
            notes.append(
                f"{len(unconfirmed)} candidate(s) match the need but compatibility is unknown for at least one "
                "requirement (the catalog does not say). Present them only as unconfirmed."
            )
        if len(confirmed) > len(shown):
            notes.append(f"{len(confirmed)} confirmed products in total; showing the top {len(shown)}.")

        return Recommendation(
            request=request,
            best_match=best.product.id if best else None,
            confirmed=[_ranked(c, results[c.product.id]) for c in shown],
            unconfirmed=[_ranked(c, results[c.product.id]) for c in unconfirmed[: request.limit]],
            excluded=excluded,
            upsell=upsell,
            accessories=accessories,
            notes=notes,
            upsell_blockers=blockers,
        )
