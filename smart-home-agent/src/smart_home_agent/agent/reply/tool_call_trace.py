from typing import Any

from pydantic import BaseModel


class ToolCallTrace(BaseModel):
    """One tool call of a turn and its response (None while it has not answered)."""

    call_id: str | None
    name: str
    args: dict[str, Any]
    response: dict[str, Any] | None = None

    @property
    def status(self) -> str | None:
        return (self.response or {}).get("status")
