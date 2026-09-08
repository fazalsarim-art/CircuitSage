"""Structured error envelope and exception handlers.

Every error response uses the stable shape (§8.9)::

    {"error": {"code": ..., "message": ..., "request_id": ..., "details": {}}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx

_logger = logging.getLogger("app.error")


class APIError(Exception):
    """Raise to return a structured error response with an explicit code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def _envelope(status_code: int, code: str, message: str, details: dict) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id_ctx.get(),
                "details": details,
            }
        },
    )


async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return _envelope(exc.status_code, exc.code, exc.message, exc.details)


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = exc.detail if isinstance(exc.detail, str) and " " not in exc.detail else "http_error"
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return _envelope(exc.status_code, code, message, {})


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "loc": [str(part) for part in err.get("loc", [])],
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    return _envelope(422, "validation_error", "Request validation failed.", {"errors": errors})


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _logger.exception("unhandled_error")
    return _envelope(500, "internal_error", "An unexpected error occurred.", {})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
