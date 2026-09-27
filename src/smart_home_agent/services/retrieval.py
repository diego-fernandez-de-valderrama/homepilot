"""Candidate discovery: semantic (Qdrant) and structured (PostgreSQL), merged by product id."""

from smart_home_agent.models import Product, ProductFilter, SearchCandidate, SearchHit, SearchResult
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.repositories.qdrant import SemanticIndex


def merge(*groups: list[SearchCandidate]) -> dict[str, float | None]:
    """product id -> best semantic score (None when only the structured path found it)."""
    merged: dict[str, float | None] = {}
    for group in groups:
        for candidate in group:
            current = merged.get(candidate.product_id)
            if candidate.score is not None and (current is None or candidate.score > current):
                merged[candidate.product_id] = candidate.score
            else:
                merged.setdefault(candidate.product_id, current)
    return merged


class RetrievalService:
    def __init__(self, catalog: CatalogReader, index: SemanticIndex) -> None:
        self._catalog = catalog
        self._index = index

    def semantic_search(self, query: str, category: str | None, limit: int) -> SearchResult:
        """Semantic discovery; everything returned is hydrated from PostgreSQL."""
        candidates = self._index.search(self._index.embed(query), category, limit)
        scores = {c.product_id: c.score for c in candidates}
        products = self._catalog.get_products(list(scores))
        return SearchResult(
            query=query,
            category=category,
            hits=[SearchHit(score=round(scores[p.id] or 0.0, 4), product=p.summary()) for p in products],
        )

    def candidates(
        self, need: str, criteria: ProductFilter, pool: int
    ) -> tuple[list[Product], dict[str, float | None]]:
        """Union of the semantic top-`pool` and the structured matches, with a semantic score for each."""
        vector = self._index.embed(need)
        semantic = self._index.search(vector, criteria.category, pool)
        _, structured_products = self._catalog.filter_products(criteria.model_copy(update={"limit": pool}))
        structured = [SearchCandidate(p.id, None, "structured") for p in structured_products]
        scores = merge(semantic, structured)
        unscored = [pid for pid, s in scores.items() if s is None]
        scores.update(self._index.score(vector, unscored))
        return self._catalog.get_products(list(scores)), scores
