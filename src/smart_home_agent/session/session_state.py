from typing import Any

from pydantic import BaseModel, Field

from smart_home_agent.models import CartItem, UpsellSuggestion
from smart_home_agent.session.central_units_asked import CentralUnitsAsked


class SessionState(BaseModel):
    """Everything the agent keeps about one conversation, stored whole under `STATE_KEY`."""

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
    central_units_asked: CentralUnitsAsked | None = None

    @property
    def must_support(self) -> list[str]:
        return [*self.user_ecosystems, *self.user_protocols]
