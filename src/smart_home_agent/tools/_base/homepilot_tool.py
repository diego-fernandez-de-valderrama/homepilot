from typing import Any

from pydantic import BaseModel, ValidationError

from smart_home_agent.services import Vocabulary
from smart_home_agent.tools._base.invalid_tool_input import InvalidToolInput

ToolResult = dict[str, Any]


class HomePilotTool:
    """Base of every tool class: the shared steps of a tool method (resolve free text, validate the arguments,
    build the "ok" result). Each subclass has one public method, the ADK tool, named like the tool."""

    @staticmethod
    def ok(**payload: Any) -> ToolResult:
        return {"status": "ok", **payload}

    @staticmethod
    def validated[M: BaseModel](model: type[M], **values: Any) -> M:
        """Validates tool arguments into `model`; errors become InvalidToolInput with the field names."""
        try:
            return model(**values)
        except ValidationError as exc:
            errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
            raise InvalidToolInput("; ".join(errors)) from exc

    @staticmethod
    def category(value: str | None) -> str | None:
        return Vocabulary.resolve_category(value) if value and value.strip() else None

    @staticmethod
    def devices(values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return list(dict.fromkeys(Vocabulary.resolve_owned_device(v) for v in values if v.strip()))
