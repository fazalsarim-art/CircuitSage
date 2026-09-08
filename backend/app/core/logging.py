"""Structured JSON logging with a per-request correlation id.

Every log line is emitted as a single JSON object including the current ``request_id``
(set by the request middleware) plus any structured ``extra`` fields such as
``duration_ms``, ``method``, ``path``, ``status_code`` and ``event``.
"""

import json
import logging
import sys
from contextvars import ContextVar

# Populated per-request by the middleware in app.main.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_STRUCTURED_FIELDS = ("event", "method", "path", "status_code", "duration_ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Route the root logger and uvicorn loggers through the JSON formatter."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
