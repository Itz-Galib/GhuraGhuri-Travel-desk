"""In-app notifications endpoints (spec 04)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.core.pagination import PageParams, page_of, page_params
from app.core.security import utcnow
from app.modules.notifications import service
from app.modules.notifications.models import Notification
from app.modules.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID | None
    channel: str
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


@router.get("")
def list_notifications(
    pagination: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    items, total = service.list_user_notifications(
        db, user_id=user.id, offset=offset, limit=pagination.page_size
    )
    return page_of(
        [NotificationResponse.model_validate(n) for n in items],
        total=total,
        params=pagination,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> NotificationResponse:
    notif = db.get(Notification, notification_id)
    if notif is None or notif.user_id != user.id:
        raise NotFoundError("Notification not found")
    if notif.read_at is None:
        notif.read_at = utcnow()
        db.commit()
        db.refresh(notif)
    return NotificationResponse.model_validate(notif)
