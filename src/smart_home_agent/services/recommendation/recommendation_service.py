from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models import (
    AccessorySuggestion,
    CompatibilityResult,
    Product,
    ProductFilter,
    Recommendation,
    RecommendationRequest,
    UpsellSuggestion,
)
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services.accessories import AccessoryService
from smart_home_agent.services.compatibility import CompatibilityEvaluator
from smart_home_agent.services.recommendation._notes import recommendation_notes
from smart_home_agent.services.recommendation._ranked_product import to_ranked_product
from smart_home_agent.services.recommendation._version_lister import VersionLister
from smart_home_agent.services.recommendation.hard_filter import HardFilter
from smart_home_agent.services.recommendation.ranker import Ranker
from smart_home_agent.services.recommendation.ranking_candidate import RankingCandidate
from smart_home_agent.services.recommendation.upsell_selector import UpsellSelector
from smart_home_agent.services.retrieval import RetrievalService
from smart_home_agent.services.vocabulary import Vocabulary


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
        self._accessories = accessories
        self._versions = VersionLister(catalog)
        self._pool = candidate_pool
        self._upsell_min_relevance = upsell_min_relevance

    def recommend(self, request: RecommendationRequest) -> Recommendation:
        terms = [Vocabulary.term(canonical) for canonical in request.must_support]
        criteria = ProductFilter(
            category=request.category,
            min_price=request.min_price,
            max_price=request.max_price,
            brands=request.brands,
            supports=request.must_support,
        )
        # 1-2. Candidates (Qdrant top-K and PostgreSQL matches), hydrated from PostgreSQL.
        products, scores = self._retrieval.candidates(request.need, criteria, self._pool)
        # 3. Hard filters.
        passed, excluded = self._hard_filter(products, criteria)
        # 4. Compatibility gate: unsupported products are excluded, unknown ones are only listed as unconfirmed.
        results = {p.id: CompatibilityEvaluator.evaluate(p, terms, request.owned_devices) for p in passed}
        # 5. Price-neutral ranking.
        candidates = Ranker.rank(Ranker.build_candidates(passed, scores, request.need, results))
        confirmed = [c for c in candidates if results[c.product.id].overall is FactStatus.SUPPORTED]
        unconfirmed = [c for c in candidates if results[c.product.id].overall is FactStatus.UNKNOWN]
        unsupported = len(candidates) - len(confirmed) - len(unconfirmed)
        if unsupported:
            excluded["unsupported"] = unsupported
        # 6. Upselling, from confirmed products only.
        best = confirmed[0] if confirmed else None
        upsell, accessories, blockers = self._upsell(best, confirmed, results, request) if best else (None, [], {})

        # One slot per product: a product with a confirmed version is not listed again as unconfirmed.
        confirmed_products = VersionLister.one_per_product(confirmed)
        unconfirmed_products = VersionLister.one_per_product(unconfirmed, frozenset(c.product.title for c in confirmed))
        shown = self._shortlist(confirmed_products, confirmed, upsell, request.limit)
        listed_unconfirmed = unconfirmed_products[: request.limit]
        versions = self._versions.other_versions(
            [*shown, *listed_unconfirmed], results, criteria, terms, request.owned_devices
        )

        return Recommendation(
            request=request,
            best_match=best.product.id if best else None,
            confirmed=[to_ranked_product(c, results[c.product.id], versions[c.product.id]) for c in shown],
            unconfirmed=[
                to_ranked_product(c, results[c.product.id], versions[c.product.id]) for c in listed_unconfirmed
            ],
            excluded=excluded,
            upsell=upsell,
            accessories=accessories,
            notes=recommendation_notes(
                len(confirmed_products), len(unconfirmed_products), len(shown), any(versions.values())
            ),
            upsell_blockers=blockers,
        )

    @staticmethod
    def _hard_filter(products: list[Product], criteria: ProductFilter) -> tuple[list[Product], dict[str, int]]:
        """(products that pass, rejection reason -> number of products)."""
        excluded: dict[str, int] = {}
        passed = []
        for product in products:
            reason = HardFilter.rejection_reason(product, criteria)
            if reason:
                excluded[reason] = excluded.get(reason, 0) + 1
            else:
                passed.append(product)
        return passed, excluded

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
        upsell = UpsellSelector.select(eligible, best, request.max_price, self._upsell_min_relevance)
        blockers: dict[str, int] = {}
        if not upsell:
            blockers = UpsellSelector.blockers(others, best, request.max_price, self._upsell_min_relevance)
            # Candidates that pass every ranking rule can only have been dropped by the extra-hub filter.
            needs_hub = sum(
                1
                for c in others
                if not UpsellSelector.rejection(c, best, request.max_price, self._upsell_min_relevance)
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

    @staticmethod
    def _shortlist(
        confirmed_products: list[RankingCandidate],
        confirmed: list[RankingCandidate],
        upsell: UpsellSuggestion | None,
        limit: int,
    ) -> list[RankingCandidate]:
        """The confirmed entries to show, within `limit`, always including the upsell."""
        shown = confirmed_products[:limit]
        if upsell and upsell.product_id not in {c.product.id for c in shown}:
            target = next(c for c in confirmed if c.product.id == upsell.product_id)
            # The upsell is the version the agent must present, so it takes its product's slot, or the last
            # slot: the list stays within the limit, except that the best match and its upsell are always both
            # listed (a limit of 1 shows 2).
            others = [c for c in shown if c.product.title != target.product.title]
            shown = [*others[: max(limit - 1, 1)], target]
        return shown
