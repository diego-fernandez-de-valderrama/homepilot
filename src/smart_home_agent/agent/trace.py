"""Per-turn trace of tool calls, for the optional developer panel (never shown to customers)."""

from typing import Any

from pydantic import BaseModel, Field

from smart_home_agent.agent.state import SessionState

_INTENTS = {
    "recommend_products": "recommendation",
    "search_products": "discovery",
    "filter_products": "structured filter",
    "get_product": "product details",
    "check_compatibility": "compatibility check",
    "compare_products": "comparison",
    "get_evidence": "provenance",
    "remember_preferences": "preferences",
}


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
        names = [c.name for c in self.tool_calls if c.name != "remember_preferences"]
        if names:
            return _INTENTS.get(names[0], names[0])
        return "preferences" if self.tool_calls else "conversation (no tool used)"

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
