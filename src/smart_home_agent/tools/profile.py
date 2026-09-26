from google.adk.tools import ToolContext

from smart_home_agent.agent.state import PROFILE_KEY
from smart_home_agent.services.profile import ProfileService
from smart_home_agent.tools._common import ToolResult, ok, tool_errors


def _message_text(tool_context: ToolContext) -> str | None:
    """Text of the customer's message that started this turn (None for a cart confirmation)."""
    content = tool_context.user_content
    parts = [part.text for part in (content.parts or []) if part.text] if content else []
    return "\n".join(parts) or None


def make_remember_customer_facts(profiles: ProfileService):
    @tool_errors
    def remember_customer_facts(
        tool_context: ToolContext,
        evidence: str,
        name: str | None = None,
        language: str | None = None,
        ecosystems: list[str] | None = None,
        hubs: list[str] | None = None,
        owned_devices: list[str] | None = None,
        preferences: list[str] | None = None,
        no_longer_used: list[str] | None = None,
        no_longer_owned: list[str] | None = None,
    ) -> ToolResult:
        """Remember lasting facts the customer stated about THEMSELF, for this and future conversations.
        Only facts from the customer's latest message, never guesses, cart contents or facts about other
        people (a friend, family, a gift recipient). Pass only the fields the message states.
        A fact mentioned together with a request also counts, e.g. "Ich habe Alexa zu Hause und suche eine
        Steckdose" states that the customer uses Alexa.

        Args:
          evidence: The customer's exact words from their latest message that state the facts, copied
            verbatim (e.g. "I use HomeKit and I have a Hue Bridge").
          name: The customer's own name.
          language: Preferred conversation language, "en" or "de".
          ecosystems: Ecosystems or voice assistants the customer uses, e.g. ["Apple HomeKit", "Alexa"].
          hubs: Bridges, hubs, gateways, access points or connectors the customer owns, e.g. ["Hue Bridge",
            "Homematic IP Access Point", "Zigbee bridge"].
          owned_devices: Other smart home hardware the customer owns, e.g. ["Sonos speaker", "Echo Dot"].
          preferences: Lasting preferences in the customer's words, e.g. ["prefers battery-powered devices"].
          no_longer_used: Ecosystems or voice assistants the customer stopped using.
          no_longer_owned: Hubs or hardware the customer no longer owns (sold, broken, given away).
        """
        update = profiles.remember(
            tool_context.user_id,
            tool_context.session.id,
            _message_text(tool_context),
            evidence,
            name=name,
            language=language,
            ecosystems=ecosystems,
            hubs=hubs,
            owned_devices=owned_devices,
            preferences=preferences,
            no_longer_used=no_longer_used,
            no_longer_owned=no_longer_owned,
        )
        if update.added or update.retracted:  # the rest of this turn sees the new profile
            tool_context.state[PROFILE_KEY] = update.profile.model_dump(mode="json")
        return ok(
            added=[f"{f.kind.value}: {f.value}" for f in update.added],
            removed=[f"{f.kind.value}: {f.value}" for f in update.retracted],
            already_known=update.unchanged,
            not_stored=[r.model_dump(mode="json", exclude_none=True) for r in update.rejected],
            profile=[f"{f.kind.value}: {f.value}" for f in update.profile.active()],
        )

    return remember_customer_facts
