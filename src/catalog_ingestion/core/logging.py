"""Structured logging: key=value records on stderr, rendered through rich when interactive."""

import logging
import sys
from typing import Any

from rich.logging import RichHandler


class KeyValueFormatter(logging.Formatter):
    """Appends `extra={"fields": {...}}` to the message as `key=value` pairs."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        fields: dict[str, Any] | None = getattr(record, "fields", None)
        if fields:
            rendered = " ".join(f"{key}={value!r}" for key, value in fields.items())
            message = f"{message} {rendered}"
        return message


def configure_logging(level: str = "INFO") -> None:
    handler: logging.Handler
    if sys.stderr.isatty():
        handler = RichHandler(show_path=False, rich_tracebacks=True)
        handler.setFormatter(KeyValueFormatter("%(name)s: %(message)s"))
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(KeyValueFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "google_genai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_fields(**fields: Any) -> dict[str, Any]:
    """Helper for `logger.info("msg", extra=log_fields(product_id=...))`."""
    return {"fields": fields}
