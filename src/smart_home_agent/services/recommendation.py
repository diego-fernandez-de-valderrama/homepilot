"""Recommendation pipeline, enforced in code:

requirements -> candidates (semantic + structured) -> hard filters -> compatibility gate
-> ranking -> upselling.

Only `confirmed` products (every requested term supported) can be the best match or the upsell.
An upsell must not need a hub that the best match does not need (its price difference would understate the
real extra cost). Required hubs the customer may not own are offered as accessories, from the catalog.
`unconfirmed` products (some term unknown) are returned separately so the agent can mention them
honestly; `unsupported` products are excluded.

Versions of one product (same title: another color, size or pack) take one slot, the best-ranked version.
The other versions are listed on that entry with their own result for the same request, and a version is
never the upsell of its own product (the capability difference between versions comes from gaps in the
catalog attributes, not from the product).
"""

from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models.compatibility import CompatibilityResult
from smart_home_agent.models.product import Product
from smart_home_agent.models.recommendation import (
    AccessorySuggestion,
    RankedProduct,
    Recommendation,
    RecommendationRequest,
    UpsellSuggestion,
    VersionOption,
    VersionStatus,
)
from smart_home_agent.models.search import ProductFilter
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services import compatibility, ranking, vocabulary
from smart_home_agent.services.accessories import AccessoryService
from smart_home_agent.services.filtering import rejection_reason
from smart_home_agent.services.ranking import RankingCandidate
from smart_home_agent.services.retrieval import RetrievalService
from smart_home_agent.services.vocabulary import ResolvedTerm

_VERSION_STATUS: dict[FactStatus, VersionStatus] = {
    FactStatus.SUPPORTED: "confirmed",
    FactStatus.UNKNOWN: "unconfirmed",
    FactStatus.UNSUPPORTED: "unsupported",
}


def one_per_product(candidates: list[RankingCandidate], taken: frozenset[str] = frozenset()) -> list[RankingCandidate]:
    """The best-ranked version of each product (versions share the title); titles in `taken` are skipped."""
    seen = set(taken)
    kept = []
    for candidate in candidates:
        if candidate.product.title not in seen:
            seen.add(candidate.product.title)
            kept.append(candidate)
    return kept


def _ranked(
    candidate: RankingCandidate, result: CompatibilityResult, other_versions: list[VersionOption]
) -> RankedProduct:
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
        other_versions=other_versions,
    )


class RecommendationService:
    def __init__(
        self,
        retrieval: RetrievalService,
        accessories: AccessoryService,
        catalog: CatalogReader,
        candidate_pool: int,
        upsell_min_relevance: float,
    ) -> None:
        self._retrieval = retrieval
        self._catalog = catalog
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
        # Another version of the best match (color, size, pack) is not an upgrade of it.
        others = [c for c in confirmed if c.product.title != best.product.title]
        eligible = [c for c in others if c.needed_hubs <= best.needed_hubs]
        upsell = ranking.select_upsell(eligible, best, request.max_price, self._upsell_min_relevance)
        blockers: dict[str, int] = {}
        if not upsell:
            blockers = ranking.upsell_blockers(others, best, request.max_price, self._upsell_min_relevance)
            # Candidates that pass every ranking rule can only have been dropped by the extra-hub filter.
            needs_hub = sum(
                1
                for c in others
                if not ranking.upsell_rejection(c, best, request.max_price, self._upsell_min_relevance)
            )
            if needs_hub:
                blockers["needs_extra_hub"] = needs_hub
            versions = sum(1 for c in confirmed if c is not best and c.product.title == best.product.title)
            if versions:
                blockers["other_version_of_best"] = versions
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
        candidates = ranking.rank(ranking.build_candidates(passed, scores, request.need, results))
        confirmed = [c for c in candidates if results[c.product.id].overall is FactStatus.SUPPORTED]
        unconfirmed = [c for c in candidates if results[c.product.id].overall is FactStatus.UNKNOWN]
        unsupported = len(candidates) - len(confirmed) - len(unconfirmed)
        if unsupported:
            excluded["unsupported"] = unsupported

        best = confirmed[0] if confirmed else None
        upsell, accessories, blockers = self._upsell(best, confirmed, results, request) if best else (None, [], {})
        # One slot per product: a product with a confirmed version is not listed again as unconfirmed.
        confirmed_products = one_per_product(confirmed)
        unconfirmed_products = one_per_product(unconfirmed, frozenset(c.product.title for c in confirmed))
        shown = confirmed_products[: request.limit]
        if upsell and upsell.product_id not in {c.product.id for c in shown}:
            target = next(c for c in confirmed if c.product.id == upsell.product_id)
            # The upsell is the version the agent must present, so it takes its product's slot.
            shown = [c for c in shown if c.product.title != target.product.title] + [target]
        listed_unconfirmed = unconfirmed_products[: request.limit]
        versions = self._other_versions([*shown, *listed_unconfirmed], results, criteria, terms, request)

        notes: list[str] = []
        if not confirmed:
            notes.append("No candidate is confirmed for every requirement; do not present any product as compatible.")
        if unconfirmed_products:
            notes.append(
                f"{len(unconfirmed_products)} candidate(s) match the need but compatibility is unknown for at least "
                "one requirement (the catalog does not say). Present them only as unconfirmed."
            )
        if len(confirmed_products) > len(shown):
            notes.append(f"{len(confirmed_products)} confirmed products in total; showing the top {len(shown)}.")
        if any(versions.values()):
            notes.append(
                "Versions of the same product (same title) share one entry; `other_versions` lists the others "
                "with their own status for this request."
            )

        return Recommendation(
            request=request,
            best_match=best.product.id if best else None,
            confirmed=[_ranked(c, results[c.product.id], versions[c.product.id]) for c in shown],
            unconfirmed=[_ranked(c, results[c.product.id], versions[c.product.id]) for c in listed_unconfirmed],
            excluded=excluded,
            upsell=upsell,
            accessories=accessories,
            notes=notes,
            upsell_blockers=blockers,
        )

    def _other_versions(
        self,
        entries: list[RankingCandidate],
        results: dict[str, CompatibilityResult],
        criteria: ProductFilter,
        terms: list[ResolvedTerm],
        request: RecommendationRequest,
    ) -> dict[str, list[VersionOption]]:
        """Entry id -> the other versions of its product, each checked against the same request
        (hard filters, then the compatibility gate), whether it was a candidate or not."""
        by_title = self._catalog.get_versions([c.product.title for c in entries]) if entries else {}
        return {
            c.product.id: [
                _version_option(v, results, criteria, terms, request.owned_devices)
                for v in by_title.get(c.product.title, [])
                if v.id != c.product.id
            ]
            for c in entries
        }


def _version_option(
    version: Product,
    results: dict[str, CompatibilityResult],
    criteria: ProductFilter,
    terms: list[ResolvedTerm],
    owned_devices: list[str] | None,
) -> VersionOption:
    base = version.version().model_dump()
    result = results.get(version.id)
    if result is None:
        reason = rejection_reason(version, criteria)
        if reason:
            return VersionOption(**base, status="filtered_out", filter_reason=reason)
        result = compatibility.evaluate(version, terms, owned_devices)
    return VersionOption(**base, status=_VERSION_STATUS[result.overall])
