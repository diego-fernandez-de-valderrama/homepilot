from catalog_ingestion.domain.enums import Dimension
from google.adk.tools import ToolContext

from smart_home_agent.agent import state
from smart_home_agent.services import vocabulary
from smart_home_agent.tools._common import ToolResult, ok, resolve_category, resolve_devices, tool_errors


def make_remember_preferences():
    @tool_errors
    def remember_preferences(
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
        session = state.load(tool_context)
        if language is not None:
            session.language = language.strip().lower()[:2] or None
        if ecosystems is not None or protocols is not None:
            resolved = vocabulary.resolve_terms([*(ecosystems or []), *(protocols or [])])
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
            session.current_category = resolve_category(category)
        if owned_devices is not None:
            session.owned_devices = resolve_devices(owned_devices)
        if requirements is not None:
            session.requirements = [r.strip() for r in requirements if r.strip()]
        state.save(tool_context, session)
        return ok(session=session.model_dump(mode="json", exclude={"last_search", "candidate_products"}))

    return remember_preferences
