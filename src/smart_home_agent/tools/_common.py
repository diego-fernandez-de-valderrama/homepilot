"""Shared tool plumbing: error handling and input resolution."""

import functools
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from smart_home_agent.services import ProductNotFoundError, TermResolutionError, Vocabulary

logger = logging.getLogger(__name__)

ToolResult = dict[str, Any]


def ok(**payload: Any) -> ToolResult:
    return {"status": "ok", **payload}


class InvalidToolInput(ValueError):
    """The tool's own arguments are invalid (the model can correct them)."""


def tool_input[M: BaseModel](model: type[M], **values: Any) -> M:
    """Validates tool arguments into `model`; errors become InvalidToolInput with the field names."""
    try:
        return model(**values)
    except ValidationError as exc:
        errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
        raise InvalidToolInput("; ".join(errors)) from exc


def tool_errors[**P](func: Callable[P, ToolResult]) -> Callable[P, ToolResult]:
    """Turn expected failures into structured results the model can act on, instead of exceptions."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> ToolResult:
        try:
            return func(*args, **kwargs)
        except TermResolutionError as exc:
            return {
                "status": "needs_clarification" if exc.options else "unrecognized",
                "kind": exc.kind,
                "value": exc.value,
                "options": exc.options,
                "message": str(exc),
            }
        except ProductNotFoundError as exc:
            return {"status": "not_found", "product_ids": exc.product_ids, "message": str(exc)}
        except InvalidToolInput as exc:
            return {"status": "invalid_input", "message": str(exc)}
        except ValidationError as exc:
            # Not the tool's arguments (those raise InvalidToolInput): stored data failed validation deeper down.
            # Reporting it as invalid_input would make the model blame and retry its own arguments.
            logger.exception("tool %s failed on invalid data", getattr(func, "__name__", func))
            return {"status": "error", "message": f"The request could not be completed ({exc.title} data error)."}
        except ValueError as exc:  # a service rejected an argument value (e.g. a cart quantity)
            return {"status": "invalid_input", "message": str(exc)}
        except Exception as exc:
            logger.exception("tool %s failed", getattr(func, "__name__", func))
            return {"status": "error", "message": f"The request could not be completed ({type(exc).__name__})."}

    return wrapper


def resolve_category(value: str | None) -> str | None:
    return Vocabulary.resolve_category(value) if value and value.strip() else None


def resolve_devices(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return list(dict.fromkeys(Vocabulary.resolve_owned_device(v) for v in values if v.strip()))
