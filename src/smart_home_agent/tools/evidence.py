from smart_home_agent.container import Services
from smart_home_agent.services import EvidenceLookup
from smart_home_agent.tools._common import ToolResult, ok, tool_errors


def make_get_evidence(services: Services):
    @tool_errors
    def get_evidence(product_id: str, topic: str) -> ToolResult:
        """Where a product fact comes from (provenance): source (catalog, web or llm), field, URL,
        verbatim evidence text, method and confidence. Use it when the user asks how we know something.

        Args:
          product_id: Catalog product id.
          topic: A compatibility term (e.g. "Matter", "HomeKit"), "requirements", a field (price, title,
            brand, category, product_type, summary, key_features, use_cases, specs) or a catalog
            attribute name (e.g. "Schutzart").
        """
        result = services.evidence.get(product_id.strip(), topic)
        if not result.items and not result.provenance and result.note is None:
            result.note = f"No stored evidence for this topic. Valid topics: {EvidenceLookup.TOPICS_HELP}."
        return ok(**result.model_dump(mode="json"))

    return get_evidence
