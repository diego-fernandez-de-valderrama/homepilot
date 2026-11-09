from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.session import StateStore
from smart_home_agent.tools._base import HomePilotTool, ToolResult, tool_errors


class CompareProductsTool(HomePilotTool):
    def __init__(self, services: Services) -> None:
        self._services = services

    @tool_errors
    def compare_products(self, product_ids: list[str], tool_context: ToolContext) -> ToolResult:
        """Structured side-by-side comparison of 2-4 products from the catalog database: price, brand,
        category, product type, compatibility per ecosystem/voice assistant/protocol (supported,
        unsupported or unknown), requirements, specifications and key features.
        "not listed" means the catalog has no value, which is not a "no".

        Args:
          product_ids: 2 to 4 catalog product ids.
        """
        result = self._services.comparison.compare([pid.strip() for pid in product_ids])
        session = StateStore.load(tool_context)
        session.comparison_products = [p.id for p in result.products]
        StateStore.save(tool_context, session)
        return self.ok(**result.model_dump(mode="json"))
