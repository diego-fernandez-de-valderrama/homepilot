from google.adk.tools import ToolContext

from smart_home_agent.agent import state
from smart_home_agent.container import Services
from smart_home_agent.services import vocabulary
from smart_home_agent.tools._common import ToolResult, ok, resolve_devices, tool_errors

MAX_PRODUCTS = 10


def make_check_compatibility(services: Services):
    @tool_errors
    def check_compatibility(
        product_ids: list[str],
        requirements: list[str],
        tool_context: ToolContext,
        owned_devices: list[str] | None = None,
    ) -> ToolResult:
        """Deterministic compatibility check of products against the user's ecosystems, voice assistants
        and protocols, based only on catalog evidence.

        Status per requirement: "supported" (explicit evidence), "unsupported" (explicit negative
        evidence) or "unknown" (the catalog does not say, which is NOT the same as unsupported).
        Also reports the product's own requirements (hubs, gateways, subscriptions) and whether
        professional installation is required.

        Args:
          product_ids: Catalog product ids to check (1-10).
          requirements: Ecosystems, voice assistants or protocols, e.g. ["HomeKit", "Matter", "Zigbee"].
            May be empty to only check the product's own requirements.
          owned_devices: Hubs/gateways the user owns, e.g. ["Homematic IP Access Point"]. Omit if unknown.
        """
        if not 1 <= len(product_ids) <= MAX_PRODUCTS:
            raise ValueError(f"check between 1 and {MAX_PRODUCTS} products")
        session = state.load(tool_context)
        if owned_devices is None:
            owned_devices = session.owned_devices
        terms = vocabulary.resolve_terms(requirements)
        results = services.compatibility.check(
            [pid.strip() for pid in product_ids], terms, resolve_devices(owned_devices)
        )
        return ok(results=[r.model_dump(mode="json") for r in results])

    return check_compatibility
