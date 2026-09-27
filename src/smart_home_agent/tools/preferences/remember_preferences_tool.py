from catalog_ingestion.domain.enums import Dimension
from google.adk.tools import ToolContext

from smart_home_agent.services import Vocabulary
from smart_home_agent.session import load_state, save_state
from smart_home_agent.tools._base import HomePilotTool, ToolResult, tool_errors


class RememberPreferencesTool(HomePilotTool):
    @tool_errors
    def remember_preferences(
        self,
        tool_context: ToolContext,
        language: str | None = None,
        ecosystems: list[str] | None = None,
        protocols: list[str] | None = None,
        budget_max: float | None = None,
        category: str | None = None,
        owned_devices: list[str] | None = None,
        requirements: list[str] | None = None,
    ) -> ToolResult:
        """Store what the user told us about their home for the rest of this conversation (session only).
        Call it when the user states their ecosystem, voice assistant, protocols, budget, owned hubs or
        other needs. Stored ecosystems/protocols and budget become defaults for recommend_products.
        This is not the customer's lasting memory: when the facts are about the customer's own home and the
        remember_customer_facts tool is available, call it too, in the same step.
        Passing a value replaces the stored one; pass an empty list to clear a list.

        Args:
          language: Conversation language, "en" or "de".
          ecosystems: Ecosystems or voice assistants the user uses, e.g. ["Apple HomeKit", "Alexa"].
          protocols: Protocols the user needs, e.g. ["Zigbee"].
          budget_max: Maximum budget in EUR.
          category: The product category currently discussed.
          owned_devices: Hubs/gateways the user owns, e.g. ["Hue Bridge"]. Pass [] if they own none.
          requirements: Other stated needs in free text, e.g. ["battery powered", "outdoor use"].
        """
        session = load_state(tool_context)
        if language is not None:
            session.language = language.strip().lower()[:2] or None
        if ecosystems is not None or protocols is not None:
            resolved = Vocabulary.resolve_terms([*(ecosystems or []), *(protocols or [])])
            platforms = [t.canonical for t in resolved if t.dimension is not Dimension.PROTOCOL]
            transports = [t.canonical for t in resolved if t.dimension is Dimension.PROTOCOL]
            # A list is replaced when it was passed, or when the other list contained items of its kind.
            if ecosystems is not None or platforms:
                session.user_ecosystems = platforms
            if protocols is not None or transports:
                session.user_protocols = transports
        if budget_max is not None:
            session.budget_max = budget_max if budget_max > 0 else None
        if category is not None:
            session.current_category = self.category(category)
        if owned_devices is not None:
            session.owned_devices = self.devices(owned_devices)
        if requirements is not None:
            session.requirements = [r.strip() for r in requirements if r.strip()]
        save_state(tool_context, session)
        return self.ok(session=session.model_dump(mode="json", exclude={"last_search", "candidate_products"}))
