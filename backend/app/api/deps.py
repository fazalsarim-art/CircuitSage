"""Shared FastAPI dependencies: current user and admin-role enforcement."""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.core.security import decode_access_token
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None:
        raise APIError(401, "not_authenticated", "Authentication required.")
    try:
        payload = decode_access_token(settings, credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise APIError(401, "token_invalid", "Invalid or expired token.") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise APIError(401, "token_invalid", "Invalid or expired token.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.admin:
        raise APIError(403, "forbidden", "Administrator privileges required.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def get_embedder(settings: Annotated[Settings, Depends(get_settings)]):
    from app.services.embeddings import build_embedder

    return build_embedder(settings)


def get_vector_store(settings: Annotated[Settings, Depends(get_settings)]):
    from app.services.vector_store import build_vector_store

    return build_vector_store(settings)


def get_reranker(settings: Annotated[Settings, Depends(get_settings)]):
    from app.retrieval.reranker import build_reranker

    return build_reranker(settings)


def get_answer_client(settings: Annotated[Settings, Depends(get_settings)]):
    from app.services.answers import build_answer_client

    return build_answer_client(settings)
