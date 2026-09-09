"""FastAPI application factory for CircuitSage.

Provides the application factory, typed settings dependency, request-id middleware,
structured logging, a stable error envelope, and the system + auth routes.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    benchmark,
    chat,
    documents,
    evals,
    feedback,
    health,
    retrieval,
)
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, request_id_ctx
from app.core.ratelimit import FixedWindowRateLimiter

_request_logger = logging.getLogger("app.request")

# Paths whose responses must not carry the strict API CSP (Swagger/OpenAPI need inline assets).
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def _apply_security_headers(response: Response, settings, path: str) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    if not path.startswith(_DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", settings.content_security_policy)
    if settings.is_production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    # Interactive docs are disabled in production to shrink the attack surface.
    docs_url = None if settings.is_production else "/docs"
    redoc_url = None if settings.is_production else "/redoc"
    app = FastAPI(
        title="CircuitSage API",
        version=settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    # Per-app rate limiter for auth attempts (isolated per instance and per test).
    app.state.login_limiter = FixedWindowRateLimiter(
        max_events=settings.login_rate_limit, window_seconds=settings.login_rate_window_seconds
    )

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
            if settings.security_headers_enabled:
                _apply_security_headers(response, settings, request.url.path)
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

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(documents.jobs_router, prefix="/api/v1")
    app.include_router(retrieval.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(chat.messages_router, prefix="/api/v1")
    app.include_router(benchmark.router, prefix="/api/v1")
    app.include_router(evals.router, prefix="/api/v1")
    app.include_router(feedback.router, prefix="/api/v1")
    app.include_router(feedback.messages_router, prefix="/api/v1")
    return app


app = create_app()
