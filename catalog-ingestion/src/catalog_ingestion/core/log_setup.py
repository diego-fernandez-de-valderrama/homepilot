import logging
import sys
from typing import Any

from rich.logging import RichHandler

from catalog_ingestion.core._key_value_formatter import KeyValueFormatter


class LogSetup:
    """Structured logging: key=value records on stderr, rendered through rich when interactive."""

    _NOISY_LOGGERS = ("httpx", "httpcore", "google_genai", "urllib3")

    @staticmethod
    def configure(level: str = "INFO") -> None:
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
        for noisy in LogSetup._NOISY_LOGGERS:
            logging.getLogger(noisy).setLevel(logging.WARNING)

    @staticmethod
    def fields(**fields: Any) -> dict[str, Any]:
        """For `logger.info("msg", extra=LogSetup.fields(product_id=...))`."""
        return {"fields": fields}
