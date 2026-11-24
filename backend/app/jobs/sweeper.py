"""Sweeper job to expire unpaid holds and seat-count reconciliation (spec 00 A4, 03 Inv 1)."""

import hmac

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db_session
from app.core.errors import ForbiddenError
from app.core.security import utcnow
from app.modules.bookings.models import ACTIVE_BOOKING_STATUSES, Booking, BookingEvent
from app.modules.bookings.repository import release_seats_atomic
from app.modules.notifications.service import create_notification
from app.modules.tours.models import Departure

internal_router = APIRouter(prefix="/internal/cron", tags=["internal"])


def expire_stale_bookings(db: Session) -> int:
    now = utcnow()
    stale = list(
        db.scalars(
            select(Booking).where(
                Booking.status == "PENDING_PAYMENT",
                Booking.expires_at.is_not(None),
                Booking.expires_at <= now,
            )
        )
    )
    for b in stale:
        b.status = "EXPIRED"
        release_seats_atomic(db, departure_id=b.departure_id, seats=b.seats)
        db.add(
            BookingEvent(
                booking_id=b.id,
                from_status="PENDING_PAYMENT",
                to_status="EXPIRED",
                actor_id=None,
                note="Booking hold expired",
            )
        )
        if b.user_id:
            create_notification(
                db,
                user_id=b.user_id,
                booking_id=b.id,
                title="Booking expired",
                body=(
                    f"Your booking {b.reference} expired because payment was not submitted in time."
                ),
            )
    db.commit()
    return len(stale)


def reconcile_departure_seats(db: Session, *, fix: bool = False) -> list[dict[str, object]]:
    """Verify Invariant 1: departures.seats_booked == sum(seats) of active bookings."""
    drifts: list[dict[str, object]] = []
    deps = list(db.scalars(select(Departure)))
    for dep in deps:
        actual = int(
            db.scalar(
                select(func.coalesce(func.sum(Booking.seats), 0)).where(
                    Booking.departure_id == dep.id,
                    Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                )
            )
            or 0
        )
        if dep.seats_booked != actual:
            drifts.append(
                {
                    "departure_id": str(dep.id),
                    "recorded": dep.seats_booked,
                    "actual": actual,
                }
            )
            if fix:
                dep.seats_booked = actual
    if fix and drifts:
        db.commit()
    return drifts


@internal_router.post("/sweep")
def trigger_sweep(
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    db: Session = Depends(get_db_session),
) -> dict[str, int]:
    expected = get_settings().internal_cron_secret.get_secret_value()
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected):
        raise ForbiddenError("Invalid cron secret")
    expired = expire_stale_bookings(db)
    return {"expired": expired}
