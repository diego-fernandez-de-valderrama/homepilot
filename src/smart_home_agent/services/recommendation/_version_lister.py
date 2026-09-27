"""Versions of one product (same title: another color, size or pack) share one entry of the recommendation."""

from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models import CompatibilityResult, Product, ProductFilter, VersionOption, VersionStatus
from smart_home_agent.repositories import CatalogReader
from smart_home_agent.services.compatibility import CompatibilityEvaluator
from smart_home_agent.services.recommendation.hard_filter import HardFilter
from smart_home_agent.services.recommendation.ranking_candidate import RankingCandidate
from smart_home_agent.services.vocabulary import ResolvedTerm

_VERSION_STATUS: dict[FactStatus, VersionStatus] = {
    FactStatus.SUPPORTED: "confirmed",
    FactStatus.UNKNOWN: "unconfirmed",
    FactStatus.UNSUPPORTED: "unsupported",
}


class VersionLister:
    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog

    @staticmethod
    def one_per_product(
        candidates: list[RankingCandidate], taken: frozenset[str] = frozenset()
    ) -> list[RankingCandidate]:
        """The best-ranked version of each product (versions share the title); titles in `taken` are skipped."""
        seen = set(taken)
        kept = []
        for candidate in candidates:
            if candidate.product.title not in seen:
                seen.add(candidate.product.title)
                kept.append(candidate)
        return kept

    def other_versions(
        self,
        entries: list[RankingCandidate],
        results: dict[str, CompatibilityResult],
        criteria: ProductFilter,
        terms: list[ResolvedTerm],
        owned_devices: list[str] | None,
    ) -> dict[str, list[VersionOption]]:
        """Entry id -> the other versions of its product, each checked against the same request
        (hard filters, then the compatibility gate), whether it was a candidate or not."""
        by_title = self._catalog.get_versions([c.product.title for c in entries]) if entries else {}
        return {
            c.product.id: [
                self._option(v, results, criteria, terms, owned_devices)
                for v in by_title.get(c.product.title, [])
                if v.id != c.product.id
            ]
            for c in entries
        }

    @staticmethod
    def _option(
        version: Product,
        results: dict[str, CompatibilityResult],
        criteria: ProductFilter,
        terms: list[ResolvedTerm],
        owned_devices: list[str] | None,
    ) -> VersionOption:
        base = version.version().model_dump()
        result = results.get(version.id)
        if result is None:
            reason = HardFilter.rejection_reason(version, criteria)
            if reason:
                return VersionOption(**base, status="filtered_out", filter_reason=reason)
            result = CompatibilityEvaluator.evaluate(version, terms, owned_devices)
        return VersionOption(**base, status=_VERSION_STATUS[result.overall])
