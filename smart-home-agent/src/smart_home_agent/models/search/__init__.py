"""Search and filter contracts, plus the internal candidate structure.

`ProductFilter` -> `FilterResult` (exact criteria in PostgreSQL); a semantic query -> `SearchResult` of
`SearchHit`s. `SearchCandidate` is an id found by one retrieval path before it is hydrated from PostgreSQL.
"""

from smart_home_agent.models.search.filter_result import FilterResult
from smart_home_agent.models.search.product_filter import ProductFilter
from smart_home_agent.models.search.search_candidate import SearchCandidate
from smart_home_agent.models.search.search_hit import SearchHit
from smart_home_agent.models.search.search_result import SearchResult
from smart_home_agent.models.search.types import SortOrder

__all__ = ["FilterResult", "ProductFilter", "SearchCandidate", "SearchHit", "SearchResult", "SortOrder"]
