from pydantic import BaseModel

from smart_home_agent.models.search.search_hit import SearchHit


class SearchResult(BaseModel):
    query: str
    category: str | None
    hits: list[SearchHit]
    note: str = (
        "Semantic candidates only. Prices and titles come from PostgreSQL, but relevance is not a "
        "compatibility check: use check_compatibility before claiming compatibility."
    )
