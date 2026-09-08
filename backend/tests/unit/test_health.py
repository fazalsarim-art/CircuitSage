"""Unit tests for the system health/version endpoints.

External dependency checks are overridden so these tests need no live services.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.routes import health
from app.core.config import Settings, get_settings
from app.main import create_app


def _test_settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://u:p@localhost:5432/circuitsage",
        jwt_secret="test-secret-that-is-at-least-32-chars",
        app_version="0.1.0",
    )


async def _ready_all_up() -> dict:
    return {"postgres": {"ok": True}, "qdrant": {"ok": True}}


async def _ready_pg_down() -> dict:
    return {
        "postgres": {"ok": False, "error": "OperationalError"},
        "qdrant": {"ok": True},
    }


def _client(readiness=None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _test_settings
    if readiness is not None:
        app.dependency_overrides[health.readiness_checks] = readiness
    return TestClient(app)


def test_live_returns_ok():
    response = _client(_ready_all_up).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_live_ok_even_when_dependencies_down():
    # /health/live must not depend on external services.
    response = _client(_ready_pg_down).get("/health/live")
    assert response.status_code == 200


def test_version_returns_app_version():
    response = _client(_ready_all_up).get("/version")
    assert response.status_code == 200
    assert response.json()["app_version"] == "0.1.0"


def test_ready_returns_200_when_all_up():
    response = _client(_ready_all_up).get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["dependencies"]["postgres"]["ok"] is True
    assert body["dependencies"]["qdrant"]["ok"] is True


def test_ready_returns_503_and_names_failed_dependency():
    response = _client(_ready_pg_down).get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["postgres"]["ok"] is False
    assert body["dependencies"]["postgres"]["error"] == "OperationalError"


def test_request_id_header_present():
    response = _client(_ready_all_up).get("/health/live")
    assert response.headers.get("x-request-id")


def test_settings_rejects_short_jwt_secret():
    with pytest.raises(ValueError):
        Settings(
            database_url="postgresql+psycopg://u:p@localhost:5432/db",
            jwt_secret="too-short",
        )


def test_settings_rejects_non_postgres_database_url():
    with pytest.raises(ValueError):
        Settings(
            database_url="mysql://u:p@localhost/db",
            jwt_secret="test-secret-that-is-at-least-32-chars",
        )
