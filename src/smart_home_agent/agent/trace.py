"""Per-turn trace of tool calls, for the optional developer panel (never shown to customers)."""

from typing import Any

from pydantic import BaseModel, Field

from smart_home_agent.agent.state import SessionState
from smart_home_agent.guardrail.callbacks import GuardrailReport
from smart_home_agent.models.cart import CartConfirmation
from smart_home_agent.models.rich import RichContent

_INTENTS = {
    "recommend_products": "recommendation",
    "search_products": "discovery",
    "filter_products": "structured filter",
    "get_product": "product details",
    "check_compatibility": "compatibility check",
    "compare_products": "comparison",
    "get_evidence": "provenance",
    "remember_preferences": "preferences",
    "view_cart": "cart",
    "add_to_cart": "cart",
    "remove_from_cart": "cart",
}
_BOOKKEEPING = frozenset({"remember_preferences", "view_cart"})


class ToolCallTrace(BaseModel):
    call_id: str | None
    name: str
    args: dict[str, Any]
    response: dict[str, Any] | None = None

    @property
    def status(self) -> str | None:
        return (self.response or {}).get("status")


class TurnTrace(BaseModel):
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)

    def add_call(self, call_id: str | None, name: str, args: dict[str, Any]) -> None:
        self.tool_calls.append(ToolCallTrace(call_id=call_id, name=name, args=args))

    def add_response(self, call_id: str | None, name: str, response: dict[str, Any] | None) -> None:
        for call in reversed(self.tool_calls):
            if call.response is None and (call.call_id == call_id or (call_id is None and call.name == name)):
                call.response = response
                return
        self.tool_calls.append(ToolCallTrace(call_id=call_id, name=name, args={}, response=response))

    @property
    def intent(self) -> str:
        # Bookkeeping calls (preferences, the start-of-conversation cart check) do not define the intent.
        names = [c.name for c in self.tool_calls if c.name not in _BOOKKEEPING]
        if names:
            return _INTENTS.get(names[0], names[0])
        if self.tool_calls:
            name = self.tool_calls[-1].name
            return _INTENTS.get(name, name)
        return "conversation (no tool used)"

    @property
    def search_queries(self) -> list[dict[str, Any]]:
        return [
            c.args for c in self.tool_calls if c.name in ("recommend_products", "search_products", "filter_products")
        ]

    @property
    def compatibility(self) -> list[dict[str, Any]]:
        rows = []
        for call in self.tool_calls:
            response = call.response or {}
            if call.name == "check_compatibility":
                rows.extend(
                    {
                        "product_id": r["product_id"],
                        "overall": r["overall"],
                        "checks": {c["label"]: c["status"] for c in r["checks"]},
                    }
                    for r in response.get("results", [])
                )
            if call.name == "recommend_products":
                for group in ("confirmed", "unconfirmed"):
                    rows.extend(
                        {"product_id": r["product"]["id"], "overall": r["compatibility"], "group": group}
                        for r in response.get(group, [])
                    )
        return rows


class AgentReply(BaseModel):
    text: str
    detected_language: str | None  # heuristic language of the user message ("en" | "de" | None)
    trace: TurnTrace
    state: SessionState
    guardrail: GuardrailReport | None = None  # what the input/output guardrail decided this turn
    rich: RichContent | None = None  # catalog data for the presentation tags in `text` (None: no tags)
    # Cart changes waiting for the customer's decision in the interface (answered with AgentService.confirm).
    pending_confirmations: list[CartConfirmation] = Field(default_factory=list)
