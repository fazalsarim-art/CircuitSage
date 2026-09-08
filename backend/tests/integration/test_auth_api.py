"""Integration tests for the authentication API against the local PostgreSQL.

Requires ``docker compose up -d``. Each test starts from an empty users table.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sqltext

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import create_app

PASSWORD = "password12345"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _clean_users():
    with SessionLocal() as db:
        db.execute(sqltext("DELETE FROM refresh_tokens"))
        db.execute(sqltext("DELETE FROM users"))
        db.commit()
    yield


def _register(client: TestClient, email: str = "user@example.com", password: str = PASSWORD):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def test_register_returns_normalized_user_summary(client: TestClient):
    r = _register(client, email="Alice@Example.com")
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "member"
    assert body["is_active"] is True


def test_register_password_too_short(client: TestClient):
    r = client.post("/api/v1/auth/register", json={"email": "x@example.com", "password": "short"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_duplicate_email_conflict(client: TestClient):
    _register(client, email="dup@example.com")
    r = _register(client, email="Dup@Example.com")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_exists"


def test_registration_disabled(client: TestClient):
    def _no_registration():
        return get_settings().model_copy(update={"allow_registration": False})

    client.app.dependency_overrides[get_settings] = _no_registration
    try:
        r = _register(client, email="nope@example.com")
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "registration_disabled"
    finally:
        client.app.dependency_overrides.clear()


def test_login_and_me(client: TestClient):
    _register(client, email="bob@example.com")
    r = client.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "bob@example.com"
    assert client.cookies.get("refresh_token")

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "bob@example.com"


def test_login_invalid_credentials(client: TestClient):
    _register(client, email="carol@example.com")
    r = client.post(
        "/api/v1/auth/login", json={"email": "carol@example.com", "password": "wrongpassword"}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_authentication(client: TestClient):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


def test_me_rejects_invalid_token(client: TestClient):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "token_invalid"


def test_refresh_rotates_and_detects_reuse(client: TestClient):
    _register(client, email="dave@example.com")
    login = client.post(
        "/api/v1/auth/login", json={"email": "dave@example.com", "password": PASSWORD}
    )
    r1 = login.cookies.get("refresh_token")
    assert r1

    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    assert rotated.json()["access_token"]
    r2 = rotated.cookies.get("refresh_token")
    assert r2 and r2 != r1

    # Reusing the old rotated token is rejected and revokes the whole family.
    client.cookies.clear()
    reuse = client.post("/api/v1/auth/refresh", cookies={"refresh_token": r1})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "invalid_or_reused_refresh"

    # The current token is now revoked too (family revocation).
    client.cookies.clear()
    after = client.post("/api/v1/auth/refresh", cookies={"refresh_token": r2})
    assert after.status_code == 401


def test_logout_revokes_refresh(client: TestClient):
    _register(client, email="erin@example.com")
    client.post("/api/v1/auth/login", json={"email": "erin@example.com", "password": PASSWORD})
    out = client.post("/api/v1/auth/logout")
    assert out.status_code == 204

    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


def test_create_admin_cli_then_login(client: TestClient):
    from app.cli import create_admin

    create_admin("admin@example.com", "adminpassword123")
    r = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "adminpassword123"}
    )
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"
