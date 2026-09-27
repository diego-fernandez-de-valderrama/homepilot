from catalog_ingestion.domain.enums import RequirementKind
from google.adk.tools import ToolContext

from smart_home_agent.container import Services
from smart_home_agent.models import CompatibilityResult
from smart_home_agent.services import Vocabulary
from smart_home_agent.session import load_state
from smart_home_agent.tools._common import ToolResult, ok, resolve_devices, tool_errors

MAX_PRODUCTS = 10
_SETUP_KINDS = (RequirementKind.HUB, RequirementKind.GATEWAY, RequirementKind.SUBSCRIPTION)
# Unknown stays unknown: no listed requirement is not proof that none exists.
_NO_SETUP_REQUIREMENT = (
    "The catalog lists no hub, gateway or subscription for this product. Say exactly that; do not claim "
    "that it works on its own unless a requirement states stand-alone operation."
)


def _with_notes(result: CompatibilityResult) -> dict:
    payload = result.model_dump(mode="json")
    if not any(r.kind in _SETUP_KINDS for r in result.requirements):
        payload["requirements_note"] = _NO_SETUP_REQUIREMENT
    return payload


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
        Also reports the product's own requirements (hubs, gateways, subscriptions; `necessity` says
        whether they are required or only needed for some features), whether professional installation
        is required, and `accessories`: the catalog hub/gateway products for required hubs the customer
        may not own, with the bundle total.

        Args:
          product_ids: Catalog product ids to check (1-10).
          requirements: Ecosystems, voice assistants or protocols, e.g. ["HomeKit", "Matter", "Zigbee"].
            May be empty to only check the product's own requirements.
          owned_devices: Hubs/gateways the user owns, e.g. ["Homematic IP Access Point"]. Omit if unknown.
        """
        if not 1 <= len(product_ids) <= MAX_PRODUCTS:
            raise ValueError(f"check between 1 and {MAX_PRODUCTS} products")
        session = load_state(tool_context)
        if owned_devices is None:
            owned_devices = session.owned_devices
        terms = Vocabulary.resolve_terms(requirements)
        results = services.compatibility.check(
            [pid.strip() for pid in product_ids], terms, resolve_devices(owned_devices)
        )
        return ok(results=[_with_notes(r) for r in results])

    return check_compatibility
