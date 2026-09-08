"""Authentication business logic: user creation, credential checks, and refresh-token
rotation with token-family reuse detection.

Callers are responsible for committing the session; these functions only add/flush.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import APIError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    verify_password,
)
from app.db.models.enums import UserRole
from app.db.models.user import RefreshToken, User

# Precomputed hash used to equalise timing when an email does not exist.
_DUMMY_HASH = hash_password("timing-equalisation-placeholder")


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    role: UserRole = UserRole.member,
    is_active: bool = True,
) -> User:
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(409, "email_exists", "An account with this email already exists.") from exc
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        # Spend comparable time so a missing email is not distinguishable by timing.
        verify_password(password, _DUMMY_HASH)
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def _create_refresh_row(
    db: Session, settings: Settings, user_id: uuid.UUID, family_id: uuid.UUID | None
) -> tuple[RefreshToken, str]:
    plaintext = generate_refresh_token()
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_refresh_token(plaintext),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    db.add(row)
    db.flush()
    return row, plaintext


def issue_tokens(db: Session, settings: Settings, user: User) -> tuple[str, int, str]:
    """Return ``(access_token, expires_in, refresh_token_plaintext)`` for a fresh session."""
    access_token, expires_in = create_access_token(settings, subject=user.id, role=user.role.value)
    _, refresh_plain = _create_refresh_row(db, settings, user.id, family_id=None)
    return access_token, expires_in, refresh_plain


def _revoke_family(db: Session, family_id: uuid.UUID, now: datetime) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def rotate_refresh(
    db: Session, settings: Settings, refresh_plaintext: str
) -> tuple[str, int, str, User] | None:
    """Rotate a refresh token. Returns new ``(access, expires_in, refresh, user)`` or None.

    If a already-revoked token is presented (reuse), the entire token family is revoked.
    """
    token_hash = hash_refresh_token(refresh_plaintext)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is None:
        return None

    now = datetime.now(UTC)
    if row.revoked_at is not None:
        _revoke_family(db, row.family_id, now)
        return None
    if row.expires_at <= now:
        return None

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None

    new_row, new_plain = _create_refresh_row(db, settings, user.id, family_id=row.family_id)
    row.revoked_at = now
    row.replaced_by_id = new_row.id

    access_token, expires_in = create_access_token(settings, subject=user.id, role=user.role.value)
    return access_token, expires_in, new_plain, user


def revoke_refresh(db: Session, refresh_plaintext: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(refresh_plaintext),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
