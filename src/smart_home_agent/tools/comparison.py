from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.session import load_state, save_state
from smart_home_agent.tools._common import ToolResult, ok, tool_errors


def make_compare_products(services: Services):
    @tool_errors
    def compare_products(product_ids: list[str], tool_context: ToolContext) -> ToolResult:
        """Structured side-by-side comparison of 2-4 products from the catalog database: price, brand,
        category, product type, compatibility per ecosystem/voice assistant/protocol (supported,
        unsupported or unknown), requirements, specifications and key features.
        "not listed" means the catalog has no value, which is not a "no".

        Args:
          product_ids: 2 to 4 catalog product ids.
        """
        result = services.comparison.compare([pid.strip() for pid in product_ids])
        session = load_state(tool_context)
        session.comparison_products = [p.id for p in result.products]
        save_state(tool_context, session)
        return ok(**result.model_dump(mode="json"))

    return compare_products
