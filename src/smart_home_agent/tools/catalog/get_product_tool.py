from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.session import load_state, save_state
from smart_home_agent.tools._base import HomePilotTool, ToolResult, tool_errors


class GetProductTool(HomePilotTool):
    def __init__(self, services: Services) -> None:
        self._services = services

    @tool_errors
    def get_product(self, product_id: str, tool_context: ToolContext) -> ToolResult:
        """Full structured data of one product: price, brand, category, specs, key features, use cases,
        compatibility facts (with status and evidence), requirements, the original catalog attributes and
        `other_versions`: the same product in another color, size or pack (id, variant, subtitle, price).

        Args:
          product_id: The catalog product id, e.g. "28477998".
        """
        catalog = self._services.catalog
        product = catalog.get_product(product_id.strip())
        if product is None:
            return {"status": "not_found", "product_ids": [product_id], "message": "Unknown product id."}
        session = load_state(tool_context)
        if product.id not in session.selected_products:
            session.selected_products = [*session.selected_products, product.id][-5:]
        save_state(tool_context, session)
        payload = product.model_dump(mode="json", exclude={"provenance", "validation_notes"})
        payload["requires_professional_installation"] = product.requires_professional_installation
        versions = catalog.get_versions([product.title]).get(product.title, [])
        other_versions = [v.version().model_dump(mode="json") for v in versions if v.id != product.id]
        return self.ok(product=payload, other_versions=other_versions)
