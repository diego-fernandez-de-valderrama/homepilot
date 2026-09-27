from typing import cast

from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.models import ProductFilter, SortOrder
from smart_home_agent.services import Vocabulary
from smart_home_agent.session import load_state, save_state
from smart_home_agent.tools._base import HomePilotTool, ToolResult, tool_errors


class FilterProductsTool(HomePilotTool):
    def __init__(self, services: Services) -> None:
        self._services = services

    @tool_errors
    def filter_products(
        self,
        tool_context: ToolContext,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        brands: list[str] | None = None,
        supports: list[str] | None = None,
        product_type_contains: str | None = None,
        sort: str = "completeness",
        limit: int = 20,
    ) -> ToolResult:
        """Exact structured filtering in the catalog database ("all Zigbee plugs under 30 EUR").

        `supports` only matches products with explicit `supported` evidence, so products whose
        compatibility is unknown are not returned by that filter.

        Args:
          category: Category (key, English or German name).
          min_price: Minimum price in EUR.
          max_price: Maximum price in EUR.
          brands: Brand names, e.g. ["Bosch", "Homematic IP"].
          supports: Ecosystems, voice assistants or protocols that must be supported, e.g. ["Zigbee"].
          product_type_contains: Text that must appear in the product type or title, e.g. "Thermostat".
          sort: "completeness" (default), "price_asc" or "price_desc".
          limit: Number of results (1-50).
        """
        criteria = self.validated(
            ProductFilter,
            category=self.category(category),
            min_price=min_price,
            max_price=max_price,
            brands=brands or [],
            supports=[t.canonical for t in Vocabulary.resolve_terms(supports)],
            product_type_contains=product_type_contains or None,
            sort=cast(SortOrder, sort),  # validated by Pydantic; the tool parameter stays a plain str
            limit=max(1, min(limit, 50)),
        )
        total, products = self._services.catalog.filter_products(criteria)
        session = load_state(tool_context)
        session.last_search = {"tool": "filter_products", **criteria.model_dump(mode="json")}
        session.candidate_products = [p.id for p in products]
        session.current_category = criteria.category or session.current_category
        save_state(tool_context, session)
        return self.ok(
            criteria=criteria.model_dump(mode="json"),
            total=total,
            products=[p.summary().model_dump(mode="json") for p in products],
        )
