"""Auth business logic: registration, login, refresh rotation, lockout."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    RateLimitedError,
    UnauthenticatedError,
)
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    utcnow,
    verify_dummy_password,
    verify_password,
)
from app.modules.auth import repository
from app.modules.auth.schemas import RegisterRequest, UpdateProfileRequest
from app.modules.operators.models import Operator, OperatorMember
from app.modules.users.models import RefreshToken, User


class EmailTakenError(ConflictError):
    code = "EMAIL_TAKEN"
    message = "An account with this email already exists"


class PhoneTakenError(ConflictError):
    code = "PHONE_TAKEN"
    message = "An account with this phone already exists"


class InvalidCredentialsError(UnauthenticatedError):
    code = "INVALID_CREDENTIALS"
    message = "Invalid email/phone or password"


class AccountSuspendedError(UnauthenticatedError):
    code = "ACCOUNT_SUSPENDED"
    message = "This account is suspended"


def _as_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    raise TypeError("expected datetime")


def _new_session(
    db: Session, user: User, *, family_id: uuid.UUID | None = None
) -> tuple[str, str, int]:
    settings = get_settings()
    plain, token_hash = new_refresh_token()
    family = family_id or uuid.uuid4()
    repository.add_refresh_token(
        db,
        user_id=user.id,
        token_hash=token_hash,
        family_id=family,
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
    )
    access_token, expires_in = create_access_token(user.id, user.role)
    return access_token, plain, expires_in


def register(db: Session, payload: RegisterRequest) -> tuple[User, str, str, int]:
    email = payload.email.lower()
    if repository.get_user_by_email(db, email):
        raise EmailTakenError()
    if repository.get_user_by_phone(db, payload.phone):
        raise PhoneTakenError()
    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role="CUSTOMER",
        status="ACTIVE",
        consented_at=utcnow(),
    )
    db.add(user)
    db.flush()
    access_token, refresh_plain, expires_in = _new_session(db, user)
    db.commit()
    db.refresh(user)
    return user, access_token, refresh_plain, expires_in


def login(
    db: Session, *, identifier: str, password: str, client_ip: str
) -> tuple[User, str, str, int]:
    from app.core.rate_limit import enforce_rate_limit

    enforce_rate_limit(bucket="login:ip", identifier=client_ip, limit=10, window_seconds=60)
    enforce_rate_limit(
        bucket="login:id",
        identifier=identifier.lower(),
        limit=10,
        window_seconds=60,
    )

    user = repository.get_user_by_identifier(db, identifier)
    if user is None:
        verify_dummy_password(password)
        raise InvalidCredentialsError()

    now = utcnow()
    if user.locked_until and _as_utc(user.locked_until) > now:
        raise RateLimitedError(
            "Too many failed attempts. Try again later.",
            details={"locked_until": _as_utc(user.locked_until).isoformat()},
        )
    if user.status != "ACTIVE":
        raise AccountSuspendedError()

    if not verify_password(password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= 5:
            exponent = max(0, (user.failed_logins // 5) - 1)
            user.locked_until = now + timedelta(minutes=10 * (2**exponent))
        db.commit()
        raise InvalidCredentialsError()

    user.failed_logins = 0
    user.locked_until = None
    access_token, refresh_plain, expires_in = _new_session(db, user)
    db.commit()
    db.refresh(user)
    return user, access_token, refresh_plain, expires_in


def refresh(db: Session, raw_token: str) -> tuple[User, str, str, int]:
    token = repository.get_refresh_by_hash(db, hash_refresh_token(raw_token))
    if token is None:
        raise UnauthenticatedError("Invalid refresh token")
    now = utcnow()
    if token.revoked_at is not None:
        # Reuse of a rotated token: revoke the whole family.
        repository.revoke_family(db, token.family_id, now)
        db.commit()
        raise UnauthenticatedError("Refresh token reuse detected")
    if _as_utc(token.expires_at) <= now:
        raise UnauthenticatedError("Refresh token expired")

    user = repository.get_user_by_id(db, token.user_id)
    if user is None or user.status != "ACTIVE":
        raise AccountSuspendedError()

    token.revoked_at = now
    access_token, refresh_plain, expires_in = _new_session(db, user, family_id=token.family_id)
    db.commit()
    db.refresh(user)
    return user, access_token, refresh_plain, expires_in


def logout(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    token = repository.get_refresh_by_hash(db, hash_refresh_token(raw_token))
    if token is not None:
        repository.revoke_family(db, token.family_id, utcnow())
        db.commit()


def memberships(db: Session, user_id: uuid.UUID) -> list[tuple[Operator, str]]:
    rows = db.execute(
        select(Operator, OperatorMember.member_role)
        .join(OperatorMember, OperatorMember.operator_id == Operator.id)
        .where(OperatorMember.user_id == user_id)
        .order_by(OperatorMember.created_at)
    ).all()
    return [(row[0], row[1]) for row in rows]


def update_profile(db: Session, user: User, payload: UpdateProfileRequest) -> User:
    if payload.email is not None:
        email = str(payload.email).lower()
        existing = repository.get_user_by_email(db, email)
        if existing and existing.id != user.id:
            raise EmailTakenError()
        user.email = email
    if payload.phone is not None:
        existing = repository.get_user_by_phone(db, payload.phone)
        if existing and existing.id != user.id:
            raise PhoneTakenError()
        user.phone = payload.phone
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    db.commit()
    db.refresh(user)
    return user


def mark_refresh_reuse_for_tests(db: Session, token_hash: str) -> RefreshToken | None:
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
