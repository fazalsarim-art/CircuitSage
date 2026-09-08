"""Unit tests for password hashing, JWTs, refresh-token hashing, and role enforcement."""

import uuid

import jwt
import pytest

from app.api.deps import require_admin
from app.core.config import Settings
from app.core.errors import APIError
from app.core.security import (
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    verify_password,
)
from app.db.models.enums import UserRole


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
        "jwt_secret": "x" * 40,
    }
    base.update(overrides)
    return Settings(**base)


def test_hash_and_verify_password():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)


def test_verify_rejects_wrong_password():
    hashed = hash_password("right-password-123")
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    settings = _settings()
    user_id = uuid.uuid4()
    token, expires_in = create_access_token(settings, subject=user_id, role="admin")
    assert expires_in == settings.access_token_minutes * 60
    payload = decode_access_token(settings, token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "admin"
    assert payload["iss"] == JWT_ISSUER
    assert payload["aud"] == JWT_AUDIENCE


def test_expired_access_token_rejected():
    settings = _settings(access_token_minutes=-1)
    token, _ = create_access_token(settings, subject=uuid.uuid4(), role="member")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(settings, token)


def test_wrong_audience_rejected():
    settings = _settings()
    bad = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "member", "iss": JWT_ISSUER, "aud": "other"},
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(settings, bad)


def test_wrong_issuer_rejected():
    settings = _settings()
    bad = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "member", "iss": "evil", "aud": JWT_AUDIENCE},
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.InvalidIssuerError):
        decode_access_token(settings, bad)


def test_wrong_secret_rejected():
    settings = _settings()
    token, _ = create_access_token(settings, subject=uuid.uuid4(), role="member")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(_settings(jwt_secret="y" * 40), token)


def test_refresh_token_hash_is_deterministic_hex64():
    token = generate_refresh_token()
    hashed = hash_refresh_token(token)
    assert len(hashed) == 64
    assert hashed == hash_refresh_token(token)
    assert hashed != hash_refresh_token(generate_refresh_token())


def test_normalize_email():
    assert normalize_email("  Foo@Example.COM ") == "foo@example.com"


def test_require_admin_allows_admin_blocks_member():
    class _Admin:
        role = UserRole.admin

    class _Member:
        role = UserRole.member

    admin = _Admin()
    assert require_admin(admin) is admin

    with pytest.raises(APIError) as exc_info:
        require_admin(_Member())
    assert exc_info.value.status_code == 403
