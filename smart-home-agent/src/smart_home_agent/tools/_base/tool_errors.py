import functools
import logging
from collections.abc import Callable
from typing import Any, cast

from pydantic import ValidationError

from smart_home_agent.services import ProductNotFoundError, TermResolutionError
from smart_home_agent.tools._base.invalid_tool_input import InvalidToolInput

logger = logging.getLogger(__name__)


def tool_errors[F: Callable[..., dict[str, Any]]](func: F) -> F:
    """Turn expected failures into structured results the model can act on, instead of exceptions."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
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

    return cast(F, wrapper)  # functools.wraps keeps the name, docstring and signature ADK reads
