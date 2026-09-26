"""ADK function tools. Each tool is a thin adapter: resolve and validate input, call a service,
return a JSON-serializable dict. No database or Qdrant access happens here."""

from collections.abc import Callable
from typing import Any

from smart_home_agent.container import Services
from smart_home_agent.tools.catalog import make_filter_products, make_get_product, make_search_products
from smart_home_agent.tools.comparison import make_compare_products
from smart_home_agent.tools.compatibility import make_check_compatibility
from smart_home_agent.tools.evidence import make_get_evidence
from smart_home_agent.tools.preferences import make_remember_preferences
from smart_home_agent.tools.recommend import make_recommend_products


def build_tools(services: Services) -> list[Callable[..., dict[str, Any]]]:
    return [
        make_recommend_products(services),
        make_search_products(services),
        make_filter_products(services),
        make_get_product(services),
        make_check_compatibility(services),
        make_compare_products(services),
        make_get_evidence(services),
        make_remember_preferences(),
    ]
