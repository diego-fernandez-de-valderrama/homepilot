import logging
from typing import Any


class KeyValueFormatter(logging.Formatter):
    """Appends `extra={"fields": {...}}` to the message as `key=value` pairs."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        fields: dict[str, Any] | None = getattr(record, "fields", None)
        if fields:
            rendered = " ".join(f"{key}={value!r}" for key, value in fields.items())
            message = f"{message} {rendered}"
        return message
