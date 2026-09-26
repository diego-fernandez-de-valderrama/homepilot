"""Shared tool plumbing: error handling and input resolution."""

import functools
import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from smart_home_agent.services import vocabulary
from smart_home_agent.services.compatibility import ProductNotFoundError
from smart_home_agent.services.vocabulary import TermResolutionError

logger = logging.getLogger(__name__)

ToolResult = dict[str, Any]


def ok(**payload: Any) -> ToolResult:
    return {"status": "ok", **payload}


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
        except ValidationError as exc:
            errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
            return {"status": "invalid_input", "message": "; ".join(errors)}
        except ValueError as exc:
            return {"status": "invalid_input", "message": str(exc)}
        except Exception as exc:
            logger.exception("tool %s failed", func.__name__)
            return {"status": "error", "message": f"The catalog could not be queried ({type(exc).__name__})."}

    return wrapper


def resolve_category(value: str | None) -> str | None:
    return vocabulary.resolve_category(value) if value and value.strip() else None


def resolve_devices(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return list(dict.fromkeys(vocabulary.resolve_owned_device(v) for v in values if v.strip()))
