class StateKey:
    """Keys of the ADK session state used by HomePilot."""

    # The whole `SessionState` (written by the tools and the agent service through `StateStore.save`).
    HOMEPILOT = "homepilot"
    # Detected language of the latest user message ("en" | "de" | None), set by the agent service each turn.
    TURN_LANGUAGE = "homepilot_turn_language"
    # Guardrail report of the current turn (reset by the agent service each turn, written by the guardrail callbacks).
    GUARDRAIL = "homepilot_guardrail"
    # Last deterministic guardrail reply of the session, so the next one picks a different variant.
    GUARDRAIL_LAST_REPLY = "homepilot_guardrail_last_reply"
    # Snapshot of the customer's stored profile (models.profile.CustomerProfile as JSON), refreshed by the agent
    # service each turn and by remember_customer_facts. The memory database is the source; this is only for the
    # instruction.
    PROFILE = "homepilot_profile"
