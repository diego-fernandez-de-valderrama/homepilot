"""Recommendation pipeline, enforced in code:

requirements -> candidates (semantic + structured) -> hard filters -> compatibility gate
-> ranking -> upselling.

Only `confirmed` products (every requested term supported) can be the best match or the upsell.
`unconfirmed` products (some term unknown) are returned separately so the agent can mention them
honestly; `unsupported` products are excluded.
"""

from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models.compatibility import CompatibilityResult
from smart_home_agent.models.recommendation import RankedProduct, Recommendation, RecommendationRequest
from smart_home_agent.models.search import ProductFilter
from smart_home_agent.services import compatibility, ranking, vocabulary
from smart_home_agent.services.filtering import rejection_reason
from smart_home_agent.services.ranking import RankingCandidate
from smart_home_agent.services.retrieval import RetrievalService


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
    def __init__(self, retrieval: RetrievalService, candidate_pool: int, upsell_min_relevance: float) -> None:
        self._retrieval = retrieval
        self._pool = candidate_pool
        self._upsell_min_relevance = upsell_min_relevance

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
        upsell = ranking.select_upsell(confirmed, best, request.max_price, self._upsell_min_relevance) if best else None
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
            notes=notes,
        )
