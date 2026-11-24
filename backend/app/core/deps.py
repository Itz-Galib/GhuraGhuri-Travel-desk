"""Shared FastAPI dependencies: current user, roles, operator tenant context."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.errors import ForbiddenError, UnauthenticatedError
from app.core.security import decode_access_token
from app.modules.auth.repository import get_user_by_id
from app.modules.operators.models import Operator, OperatorMember
from app.modules.users.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthenticatedError()
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise UnauthenticatedError("Invalid access token") from exc
    user = get_user_by_id(db, user_id)
    if user is None:
        raise UnauthenticatedError("Invalid access token")
    if user.status != "ACTIVE":
        raise ForbiddenError("This account is suspended")
    return user


def require_role(*roles: str) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError()
        return user

    return dependency


@dataclass(frozen=True)
class OperatorContext:
    operator: Operator
    member_role: str

    @property
    def operator_id(self) -> uuid.UUID:
        return self.operator.id

    @property
    def is_owner(self) -> bool:
        return self.member_role == "OWNER"


def current_operator_member(
    user: User = Depends(require_role("OPERATOR")),
    db: Session = Depends(get_db_session),
) -> OperatorContext:
    row = db.execute(
        select(Operator, OperatorMember.member_role)
        .join(OperatorMember, OperatorMember.operator_id == Operator.id)
        .where(OperatorMember.user_id == user.id)
        .order_by(OperatorMember.created_at)
        .limit(1)
    ).first()
    if row is None:
        raise ForbiddenError("No operator account is linked to this user")
    return OperatorContext(operator=row[0], member_role=row[1])


def get_admin_user(user: User = Depends(require_role("ADMIN"))) -> User:
    return user
