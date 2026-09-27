from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.session import StateStore
from smart_home_agent.tools._base import HomePilotTool, ToolResult, tool_errors


class SearchProductsTool(HomePilotTool):
    def __init__(self, services: Services) -> None:
        self._services = services

    @tool_errors
    def search_products(
        self, query: str, tool_context: ToolContext, category: str | None = None, limit: int = 8
    ) -> ToolResult:
        """Semantic product discovery for open questions ("something to save heating costs").

        Results are unverified candidates ranked by semantic similarity. Titles and prices come
        from the structured catalog, but a hit says nothing about compatibility: use
        check_compatibility or recommend_products before claiming it.

        Args:
          query: Natural-language description of what the user is looking for (any language).
          category: Optional category (key, English or German name).
          limit: Number of results (1-20).
        """
        category_key = self.category(category)
        result = self._services.retrieval.semantic_search(query, category_key, max(1, min(limit, 20)))
        session = StateStore.load(tool_context)
        session.last_search = {"tool": "search_products", "query": query, "category": category_key}
        session.candidate_products = [hit.product.id for hit in result.hits]
        session.current_category = category_key or session.current_category
        StateStore.save(tool_context, session)
        return self.ok(**result.model_dump(mode="json"))
