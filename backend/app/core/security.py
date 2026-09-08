"""Password hashing (Argon2) and JWT / refresh-token primitives.

- Passwords are hashed with Argon2 via pwdlib. Raw passwords are never stored.
- Access tokens are short-lived signed JWTs (HS256) carrying issuer, audience, subject,
  role, issued-at and expiry claims.
- Refresh tokens are random high-entropy strings; only their SHA-256 hash is persisted.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings

_password_hash = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "circuitsage"
JWT_AUDIENCE = "circuitsage-api"


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_access_token(settings: Settings, *, subject: uuid.UUID, role: str) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``."""
    now = datetime.now(UTC)
    expires_delta = timedelta(minutes=settings.access_token_minutes)
    payload = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, settings.access_token_minutes * 60


def decode_access_token(settings: Settings, token: str) -> dict:
    """Decode and validate a JWT. Raises ``jwt.PyJWTError`` on any failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
    )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
