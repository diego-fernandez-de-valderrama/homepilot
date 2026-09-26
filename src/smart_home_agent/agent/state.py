"""Conversation state, kept in the ADK session (in memory, per conversation; nothing is persisted)."""

from collections.abc import Mapping
from typing import Any, Protocol

from google.adk.sessions.state import State
from pydantic import BaseModel, Field

from smart_home_agent.models.cart import CartItem
from smart_home_agent.models.recommendation import UpsellSuggestion

STATE_KEY = "homepilot"
# Detected language of the latest user message ("en" | "de" | None), set by the orchestrator each turn.
TURN_LANGUAGE_KEY = "homepilot_turn_language"
# Guardrail report of the current turn (reset by the orchestrator each turn, written by the guardrail callbacks).
GUARDRAIL_KEY = "homepilot_guardrail"
# Last deterministic guardrail reply of the session, so the next one picks a different variant.
GUARDRAIL_LAST_REPLY_KEY = "homepilot_guardrail_last_reply"
# Cart bookkeeping of SessionState: the model reads the cart through view_cart, never through the prompt.
CART_FIELDS = frozenset({"cart", "cart_checked", "cart_changed_by_user"})


class SessionState(BaseModel):
    language: str | None = None  # "en" | "de"
    user_ecosystems: list[str] = Field(default_factory=list)  # canonical ecosystems and voice assistants
    user_protocols: list[str] = Field(default_factory=list)  # canonical protocols
    owned_devices: list[str] | None = None  # canonical hubs/gateways; None = not stated yet
    budget_max: float | None = None
    requirements: list[str] = Field(default_factory=list)  # other stated needs, free text
    current_category: str | None = None
    last_search: dict[str, Any] | None = None
    candidate_products: list[str] = Field(default_factory=list)
    selected_products: list[str] = Field(default_factory=list)
    comparison_products: list[str] = Field(default_factory=list)
    last_upsell: UpsellSuggestion | None = None  # latest recommend_products upsell, the only valid <upgrade/>
    cart: list[CartItem] = Field(default_factory=list)  # ids and quantities only; data comes from PostgreSQL
    cart_checked: bool = False  # a cart tool ran in this conversation
    cart_changed_by_user: bool = False  # edited in the interface since the last cart tool call

    @property
    def must_support(self) -> list[str]:
        return [*self.user_ecosystems, *self.user_protocols]


class StateHolder(Protocol):
    """The part of ADK's ToolContext the tools use (also easy to fake in tests)."""

    @property
    def state(self) -> Any: ...


def read_state(state: Mapping[str, Any] | State) -> SessionState:
    return SessionState.model_validate(state.get(STATE_KEY) or {})


def load(context: StateHolder) -> SessionState:
    return read_state(context.state)


def save(context: StateHolder, session_state: SessionState) -> None:
    # Assign the whole value: ADK records assignments (not in-place mutations) as state deltas.
    context.state[STATE_KEY] = session_state.model_dump(mode="json")
