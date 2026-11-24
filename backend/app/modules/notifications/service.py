"""Notifications service (in-app + manual WhatsApp template text)."""

import urllib.parse
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    booking_id: uuid.UUID | None,
    title: str,
    body: str,
    channel: str = "IN_APP",
) -> Notification:
    notif = Notification(
        user_id=user_id,
        booking_id=booking_id,
        channel=channel,
        title=title,
        body=body,
    )
    db.add(notif)
    return notif


def list_user_notifications(
    db: Session, *, user_id: uuid.UUID, offset: int, limit: int
) -> tuple[list[Notification], int]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    total = int(
        db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user_id)) or 0
    )
    items = list(
        db.scalars(stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit))
    )
    return items, total


def build_unavailable_whatsapp_message(
    *, reference: str, contact_name: str, contact_phone: str, package_title: str, reason: str
) -> tuple[str, str]:
    text = (
        f"Assalamu Alaikum {contact_name}, your GhuraGhuri booking ({reference}) for "
        f"'{package_title}' could not be fulfilled: {reason}. "
        f"Our team will assist you with a full refund or alternative date."
    )
    digits = "".join(ch for ch in contact_phone if ch.isdigit())
    wa_url = f"https://wa.me/{digits}?text={urllib.parse.quote(text)}"
    return text, wa_url
