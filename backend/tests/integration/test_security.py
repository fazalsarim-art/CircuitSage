"""Integration tests for Phase 11 security controls: headers, login throttling,
daily query limits, and the safe error envelope."""

import uuid

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import text as sqltext

from app.core.config import get_settings
from app.db.models.conversation import Conversation, Message
from app.db.models.enums import MessageRole
from app.db.session import SessionLocal
from app.main import create_app

PASSWORD = "password12345"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(sqltext("DELETE FROM conversations"))
        db.execute(sqltext("DELETE FROM refresh_tokens"))
        db.execute(sqltext("DELETE FROM users"))
        db.commit()
    yield


def _member(client, email="member@example.com"):
    client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    token = r.json()["access_token"]
    from sqlalchemy import select

    from app.core.security import normalize_email
    from app.db.models.user import User

    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == normalize_email(email)))
    return {"Authorization": "Bearer " + token}, user_id


def test_security_headers_present():
    # A dedicated client so login attempts here do not consume another test's budget.
    client = TestClient(create_app())
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Request-ID"]


def test_login_throttled_after_limit():
    settings = get_settings()
    client = TestClient(create_app())
    with SessionLocal() as db:
        db.execute(sqltext("DELETE FROM refresh_tokens"))
        db.execute(sqltext("DELETE FROM users"))
        db.commit()
    client.post("/api/v1/auth/register", json={"email": "brute@example.com", "password": PASSWORD})

    statuses = []
    for _ in range(settings.login_rate_limit + 2):
        r = client.post(
            "/api/v1/auth/login", json={"email": "brute@example.com", "password": "wrong-password"}
        )
        statuses.append(r.status_code)
    assert 401 in statuses  # bad credentials while under the limit
    assert statuses[-1] == 429  # eventually throttled
    assert client.post(
        "/api/v1/auth/login", json={"email": "brute@example.com", "password": "wrong-password"}
    ).json()["error"]["code"] == "too_many_attempts"


def test_daily_query_limit_blocks_before_retrieval(client):
    member, member_id = _member(client)
    # Drop the quota to 1 and seed one used question so the next request is over budget.
    with SessionLocal() as db:
        db.execute(
            sqltext("UPDATE users SET daily_query_limit = 1 WHERE id = :id"), {"id": member_id}
        )
        conversation = Conversation(user_id=uuid.UUID(str(member_id)), title="c")
        db.add(conversation)
        db.flush()
        db.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.user,
                content="first question of the day",
                request_id=uuid.uuid4(),
            )
        )
        db.commit()
        conversation_id = str(conversation.id)

    r = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=member,
        json={"content": "another question please", "retrieval_mode": "lexical", "top_k": 5},
    )
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "daily_limit_exceeded"


def test_unhandled_exception_returns_safe_envelope(client):
    # Mount a route that raises an unexpected error and confirm no internals leak.
    app = client.app
    boom = APIRouter()

    @boom.get("/api/v1/_boom")
    def _boom():
        raise RuntimeError("secret internal detail: db password p@ss")

    app.include_router(boom)

    r = client.get("/api/v1/_boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret internal detail" not in r.text
    assert body["error"]["request_id"]
