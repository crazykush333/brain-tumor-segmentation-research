"""Structured (JSON-lines) logging."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

_LOGGER_NAME = "brats_uncertainty"


class JsonFormatter(logging.Formatter):
    """Format records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str | None = None, level: int = logging.INFO) -> logging.Logger:
    """Return a package logger with a JSON handler attached once."""
    logger = logging.getLogger(_LOGGER_NAME if name is None else f"{_LOGGER_NAME}.{name}")
    root = logging.getLogger(_LOGGER_NAME)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
        root.setLevel(level)
        root.propagate = False
    return logger


def log_event(logger: logging.Logger, msg: str, **fields: Any) -> None:
    """Log ``msg`` with structured key/value fields."""
    logger.info(msg, extra={"fields": fields})
