"""Keys of the ADK session state used by HomePilot."""

STATE_KEY = "homepilot"
# Detected language of the latest user message ("en" | "de" | None), set by the agent service each turn.
TURN_LANGUAGE_KEY = "homepilot_turn_language"
# Guardrail report of the current turn (reset by the agent service each turn, written by the guardrail callbacks).
GUARDRAIL_KEY = "homepilot_guardrail"
# Last deterministic guardrail reply of the session, so the next one picks a different variant.
GUARDRAIL_LAST_REPLY_KEY = "homepilot_guardrail_last_reply"
# Snapshot of the customer's stored profile (models.profile.CustomerProfile as JSON), refreshed by the agent service
# each turn and by remember_customer_facts. The memory database is the source; this is only for the instruction.
PROFILE_KEY = "homepilot_profile"
# Cart bookkeeping of SessionState: the model reads the cart through view_cart, never through the prompt.
CART_FIELDS = frozenset({"cart", "cart_checked", "cart_changed_by_user", "central_units_asked"})
