from collections.abc import Callable

from google.adk.tools import FunctionTool

from smart_home_agent.container import Services
from smart_home_agent.tools.cart import (
    CONFIRMED_TOOLS,
    AddToCartTool,
    CartConfirmationRule,
    RemoveFromCartTool,
    ViewCartTool,
)
from smart_home_agent.tools.catalog import FilterProductsTool, GetProductTool, SearchProductsTool
from smart_home_agent.tools.comparison import CompareProductsTool
from smart_home_agent.tools.compatibility import CheckCompatibilityTool
from smart_home_agent.tools.evidence import GetEvidenceTool
from smart_home_agent.tools.preferences import RememberPreferencesTool
from smart_home_agent.tools.profile import RememberCustomerFactsTool
from smart_home_agent.tools.recommendation import RecommendProductsTool
from smart_home_agent.tools.threaded_function_tool import ThreadedFunctionTool


class ToolRegistry:
    """Builds the agent's tools: one instance per tool class, its tool method wrapped in a
    `ThreadedFunctionTool`, and the customer's confirmation for every cart change."""

    def __init__(self, services: Services) -> None:
        self._services = services

    def build(self) -> list[FunctionTool]:
        services = self._services
        functions = [
            RecommendProductsTool(services).recommend_products,
            SearchProductsTool(services).search_products,
            FilterProductsTool(services).filter_products,
            GetProductTool(services).get_product,
            CheckCompatibilityTool(services).check_compatibility,
            CompareProductsTool(services).compare_products,
            GetEvidenceTool(services).get_evidence,
            RememberPreferencesTool().remember_preferences,
            ViewCartTool(services).view_cart,
            AddToCartTool(services).add_to_cart,
            RemoveFromCartTool(services).remove_from_cart,
        ]
        if services.profile is not None:
            functions.append(RememberCustomerFactsTool(services.profile).remember_customer_facts)
        return [ThreadedFunctionTool(f, require_confirmation=self._confirmation(f.__name__)) for f in functions]

    def _confirmation(self, name: str) -> bool | Callable[..., bool]:
        """The customer confirms every cart change in the interface before ADK runs the tool (a change refused
        at once, see CartConfirmationRule, has nothing to confirm)."""
        if action := CONFIRMED_TOOLS.get(name):
            return CartConfirmationRule(self._services, action).needs_confirmation
        return False
