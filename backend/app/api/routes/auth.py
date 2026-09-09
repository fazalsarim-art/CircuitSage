"""Authentication endpoints (§8.10).

Access tokens are returned in the JSON body (the front end keeps them in memory).
Refresh tokens live only in an HttpOnly cookie scoped to the auth path.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.core.security import normalize_email
from app.db.models.enums import UserRole
from app.db.session import get_db
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserSummary,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)]


def _set_refresh_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.post("/register", status_code=201, response_model=UserSummary)
def register(payload: RegisterRequest, db: DbDep, settings: SettingsDep) -> UserSummary:
    if not settings.allow_registration:
        raise APIError(403, "registration_disabled", "Registration is disabled.")
    user = auth_service.create_user(
        db, email=payload.email, password=payload.password, role=UserRole.member
    )
    db.commit()
    return UserSummary.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep
) -> TokenResponse:
    # Throttle brute-force attempts per client IP + email (§7.12).
    limiter = getattr(request.app.state, "login_limiter", None)
    if limiter is not None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{normalize_email(payload.email)}"
        if not limiter.allow(key):
            raise APIError(
                429, "too_many_attempts", "Too many login attempts. Try again shortly."
            )
    user = auth_service.authenticate(db, payload.email, payload.password)
    if user is None:
        raise APIError(401, "invalid_credentials", "Invalid email or password.")
    access_token, expires_in, refresh_plain = auth_service.issue_tokens(db, settings, user)
    db.commit()
    _set_refresh_cookie(response, settings, refresh_plain)
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserSummary.model_validate(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    response: Response, db: DbDep, settings: SettingsDep, refresh_token: RefreshCookie = None
) -> AccessTokenResponse:
    if not refresh_token:
        raise APIError(401, "invalid_or_reused_refresh", "Missing refresh token.")
    result = auth_service.rotate_refresh(db, settings, refresh_token)
    db.commit()
    if result is None:
        _clear_refresh_cookie(response)
        raise APIError(401, "invalid_or_reused_refresh", "Invalid or reused refresh token.")
    access_token, expires_in, new_refresh, _user = result
    _set_refresh_cookie(response, settings, new_refresh)
    return AccessTokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", status_code=204)
def logout(response: Response, db: DbDep, refresh_token: RefreshCookie = None) -> Response:
    if refresh_token:
        auth_service.revoke_refresh(db, refresh_token)
        db.commit()
    _clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser) -> MeResponse:
    return MeResponse.model_validate(user)
