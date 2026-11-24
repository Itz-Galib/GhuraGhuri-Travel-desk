"""Auth and profile endpoints (spec 04 Auth)."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.errors import ForbiddenError
from app.modules.auth import service
from app.modules.auth.schemas import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    OperatorMembership,
    RegisterRequest,
    UpdateProfileRequest,
    UserProfile,
)
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["me"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=f"{settings.api_v1_prefix}/auth",
        domain=settings.refresh_cookie_domain,
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=f"{settings.api_v1_prefix}/auth",
        domain=settings.refresh_cookie_domain,
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _auth_response(
    user: User, access_token: str, expires_in: int, response: Response, refresh_plain: str
) -> AuthResponse:
    _set_refresh_cookie(response, refresh_plain)
    return AuthResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserProfile.model_validate(user),
    )


def _me(db: Session, user: User) -> MeResponse:
    memberships = service.memberships(db, user.id)
    return MeResponse(
        user=UserProfile.model_validate(user),
        operator_memberships=[
            OperatorMembership(
                operator_id=operator.id,
                display_name=operator.display_name,
                member_role=role,
                verification_status=operator.verification_status,
            )
            for operator, role in memberships
        ],
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    from app.core.rate_limit import enforce_rate_limit

    enforce_rate_limit(
        bucket="register:ip", identifier=_client_ip(request), limit=5, window_seconds=3600
    )
    user, access_token, refresh_plain, expires_in = service.register(db, payload)
    return _auth_response(user, access_token, expires_in, response, refresh_plain)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    user, access_token, refresh_plain, expires_in = service.login(
        db,
        identifier=payload.identifier.strip(),
        password=payload.password,
        client_ip=_client_ip(request),
    )
    return _auth_response(user, access_token, expires_in, response, refresh_plain)


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        raise ForbiddenError("Missing X-Requested-With header")
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    if not raw:
        raise ForbiddenError("No refresh token cookie")
    user, access_token, refresh_plain, expires_in = service.refresh(db, raw)
    return _auth_response(user, access_token, expires_in, response, refresh_plain)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
) -> Response:
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    service.logout(db, raw)
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@me_router.get("/me", response_model=MeResponse, tags=["me"])
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db_session)) -> MeResponse:
    return _me(db, user)


@me_router.patch("/me", response_model=MeResponse, tags=["me"])
def update_me(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MeResponse:
    updated = service.update_profile(db, user, payload)
    return _me(db, updated)
