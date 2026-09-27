from typing import cast

from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.models import ProductFilter, SortOrder
from smart_home_agent.services import vocabulary
from smart_home_agent.session import load_state, save_state
from smart_home_agent.tools._common import ToolResult, ok, resolve_category, tool_errors, tool_input


def make_search_products(services: Services):
    @tool_errors
    def search_products(
        query: str, tool_context: ToolContext, category: str | None = None, limit: int = 8
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
        category_key = resolve_category(category)
        result = services.retrieval.semantic_search(query, category_key, max(1, min(limit, 20)))
        session = load_state(tool_context)
        session.last_search = {"tool": "search_products", "query": query, "category": category_key}
        session.candidate_products = [hit.product.id for hit in result.hits]
        session.current_category = category_key or session.current_category
        save_state(tool_context, session)
        return ok(**result.model_dump(mode="json"))

    return search_products


def make_filter_products(services: Services):
    @tool_errors
    def filter_products(
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
        criteria = tool_input(
            ProductFilter,
            category=resolve_category(category),
            min_price=min_price,
            max_price=max_price,
            brands=brands or [],
            supports=[t.canonical for t in vocabulary.resolve_terms(supports)],
            product_type_contains=product_type_contains or None,
            sort=cast(SortOrder, sort),  # validated by Pydantic; the tool parameter stays a plain str
            limit=max(1, min(limit, 50)),
        )
        total, products = services.catalog.filter_products(criteria)
        session = load_state(tool_context)
        session.last_search = {"tool": "filter_products", **criteria.model_dump(mode="json")}
        session.candidate_products = [p.id for p in products]
        session.current_category = criteria.category or session.current_category
        save_state(tool_context, session)
        return ok(
            criteria=criteria.model_dump(mode="json"),
            total=total,
            products=[p.summary().model_dump(mode="json") for p in products],
        )

    return filter_products


def make_get_product(services: Services):
    @tool_errors
    def get_product(product_id: str, tool_context: ToolContext) -> ToolResult:
        """Full structured data of one product: price, brand, category, specs, key features, use cases,
        compatibility facts (with status and evidence), requirements, the original catalog attributes and
        `other_versions`: the same product in another color, size or pack (id, variant, subtitle, price).

        Args:
          product_id: The catalog product id, e.g. "28477998".
        """
        product = services.catalog.get_product(product_id.strip())
        if product is None:
            return {"status": "not_found", "product_ids": [product_id], "message": "Unknown product id."}
        session = load_state(tool_context)
        if product.id not in session.selected_products:
            session.selected_products = [*session.selected_products, product.id][-5:]
        save_state(tool_context, session)
        payload = product.model_dump(mode="json", exclude={"provenance", "validation_notes"})
        payload["requires_professional_installation"] = product.requires_professional_installation
        versions = services.catalog.get_versions([product.title]).get(product.title, [])
        other_versions = [v.version().model_dump(mode="json") for v in versions if v.id != product.id]
        return ok(product=payload, other_versions=other_versions)

    return get_product
