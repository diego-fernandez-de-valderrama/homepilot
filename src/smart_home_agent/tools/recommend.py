import logging
from typing import Any

from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.models import RecommendationRequest
from smart_home_agent.services import Vocabulary
from smart_home_agent.session import load_state, save_state
from smart_home_agent.tools._common import ToolResult, ok, resolve_category, resolve_devices, tool_errors, tool_input

logger = logging.getLogger(__name__)


def make_recommend_products(services: Services):
    @tool_errors
    def recommend_products(
        need: str,
        tool_context: ToolContext,
        category: str | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
        brands: list[str] | None = None,
        must_support: list[str] | None = None,
        owned_devices: list[str] | None = None,
        limit: int = 5,
    ) -> ToolResult:
        """Main tool for product recommendations ("I need a thermostat for Google Home under 150 EUR").

        Runs the full pipeline in code: semantic + structured candidate search, hard filters
        (category, price, brand), deterministic compatibility gate, ranking and upselling.
        Returns `confirmed` products (every must_support term is supported by catalog evidence),
        `unconfirmed` products (compatibility unknown for some term, never present them as compatible),
        `excluded` counts, the `best_match` id, an optional `upsell` with factual upgrade reasons and
        `accessories`: catalog hubs/gateways that the best match or the upsell require (with the bundle total).

        Args:
          need: The user's need in their own words (any language), e.g. "smart radiator thermostat".
          category: Product category (key, English or German name), e.g. "heating_control" or "Thermostat".
          max_price: Hard budget limit in EUR. If omitted, the budget stored in the session is used.
          min_price: Minimum price in EUR.
          brands: Only these brands.
          must_support: Required ecosystems, voice assistants or protocols, e.g. ["Google Home", "Matter"].
            If omitted, the ecosystems and protocols stored in the session are used.
          owned_devices: Hubs/gateways the user already owns, e.g. ["Hue Bridge"]. Omit if unknown.
          limit: Maximum number of products per list (1-10).
        """
        session = load_state(tool_context)
        applied: dict[str, Any] = {}
        if must_support is None and session.must_support:
            must_support = session.must_support
            applied["must_support"] = must_support
        if max_price is None and session.budget_max is not None:
            max_price = session.budget_max
            applied["max_price"] = max_price
        if owned_devices is None and session.owned_devices is not None:
            owned_devices = session.owned_devices
            applied["owned_devices"] = owned_devices

        request = tool_input(
            RecommendationRequest,
            need=need,
            category=resolve_category(category),
            max_price=max_price,
            min_price=min_price,
            brands=brands or [],
            must_support=[t.canonical for t in Vocabulary.resolve_terms(must_support)],
            owned_devices=resolve_devices(owned_devices),
            limit=limit,
        )
        result = services.recommendation.recommend(request)

        session.current_category = request.category or session.current_category
        session.last_search = {"tool": "recommend_products", **request.model_dump(mode="json")}
        session.candidate_products = list(
            dict.fromkeys(
                [r.product.id for r in (*result.confirmed, *result.unconfirmed)]
                + [a.product_id for a in result.accessories]
            )
        )
        session.selected_products = [
            pid for pid in (result.best_match, result.upsell.product_id if result.upsell else None) if pid
        ]
        session.last_upsell = result.upsell
        save_state(tool_context, session)
        logger.info(
            "commerce best_match=%s upsell=%s upsell_delta=%s accessories=%s bundle_totals=%s",
            result.best_match,
            result.upsell and result.upsell.product_id,
            result.upsell and result.upsell.price_difference,
            [a.product_id for a in result.accessories],
            [a.bundle_total for a in result.accessories],
        )
        return ok(applied_from_session=applied, **result.model_dump(mode="json"))

    return recommend_products
