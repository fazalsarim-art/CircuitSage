"""FastAPI application factory for CircuitSage.

Phase 1 scope: application factory, typed settings dependency, request-id middleware,
structured logging, a safe generic error envelope, and the system health/version routes.
No document or retrieval code yet.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_ctx

_request_logger = logging.getLogger("app.request")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title="CircuitSage API", version=settings.app_version)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _request_logger.info(
                "http_request",
                extra={
                    "event": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            request_id_ctx.reset(token)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        _request_logger.exception("unhandled_error")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id_ctx.get(),
                    "details": {},
                }
            },
        )

    app.include_router(health.router)
    return app


app = create_app()
