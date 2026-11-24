"""Bookings repository. Operator queries require operator_id (spec 05)."""

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from app.modules.bookings.models import Booking, IdempotencyKey, Payment
from app.modules.tours.models import Departure, TourPackage


def reserve_seats_atomic(db: Session, *, departure_id: uuid.UUID, seats: int) -> bool:
    res = db.execute(
        text(
            "UPDATE departures "
            "SET seats_booked = seats_booked + :n "
            "WHERE id = :id AND status = 'OPEN' AND seats_booked + :n <= capacity "
            "RETURNING id"
        ),
        {"n": seats, "id": departure_id},
    ).first()
    return res is not None


def release_seats_atomic(db: Session, *, departure_id: uuid.UUID, seats: int) -> None:
    db.execute(
        text("UPDATE departures SET seats_booked = GREATEST(0, seats_booked - :n) WHERE id = :id"),
        {"n": seats, "id": departure_id},
    )


def get_idempotency_key(db: Session, *, user_id: uuid.UUID, key: str) -> IdempotencyKey | None:
    return db.get(IdempotencyKey, (user_id, key))


def get_customer_booking(
    db: Session, *, booking_id: uuid.UUID, user_id: uuid.UUID
) -> Booking | None:
    return db.scalar(
        select(Booking)
        .options(
            joinedload(Booking.travellers),
            joinedload(Booking.events),
            joinedload(Booking.payments),
        )
        .where(Booking.id == booking_id, Booking.user_id == user_id)
    )


def list_customer_bookings(
    db: Session, *, user_id: uuid.UUID, offset: int, limit: int
) -> tuple[list[Booking], int]:
    stmt = select(Booking).where(Booking.user_id == user_id)
    total = int(db.scalar(select(func.count(Booking.id)).where(Booking.user_id == user_id)) or 0)
    items = list(db.scalars(stmt.order_by(Booking.created_at.desc()).offset(offset).limit(limit)))
    return items, total


def get_operator_booking(
    db: Session, *, operator_id: uuid.UUID, booking_id: uuid.UUID
) -> Booking | None:
    return db.scalar(
        select(Booking)
        .join(Departure, Departure.id == Booking.departure_id)
        .join(TourPackage, TourPackage.id == Departure.package_id)
        .options(
            joinedload(Booking.travellers),
            joinedload(Booking.events),
            joinedload(Booking.payments),
        )
        .where(Booking.id == booking_id, TourPackage.operator_id == operator_id)
    )


def list_operator_bookings(
    db: Session,
    *,
    operator_id: uuid.UUID,
    status_filter: str | None,
    departure_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> tuple[list[Booking], int]:
    stmt = (
        select(Booking)
        .join(Departure, Departure.id == Booking.departure_id)
        .join(TourPackage, TourPackage.id == Departure.package_id)
        .where(TourPackage.operator_id == operator_id)
    )
    if status_filter:
        stmt = stmt.where(Booking.status == status_filter)
    if departure_id:
        stmt = stmt.where(Booking.departure_id == departure_id)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = list(db.scalars(stmt.order_by(Booking.created_at.desc()).offset(offset).limit(limit)))
    return items, total


def get_operator_payment(
    db: Session, *, operator_id: uuid.UUID, payment_id: uuid.UUID
) -> tuple[Payment, Booking] | None:
    row = db.execute(
        select(Payment, Booking)
        .join(Booking, Booking.id == Payment.booking_id)
        .join(Departure, Departure.id == Booking.departure_id)
        .join(TourPackage, TourPackage.id == Departure.package_id)
        .where(Payment.id == payment_id, TourPackage.operator_id == operator_id)
    ).first()
    return (row[0], row[1]) if row else None


def sum_verified_payments(db: Session, booking_id: uuid.UUID) -> int:
    val = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.booking_id == booking_id,
            Payment.status == "VERIFIED",
        )
    )
    return int(val or 0)


def txn_id_exists(db: Session, *, provider: str, provider_txn_id: str) -> bool:
    return (
        db.scalar(
            select(Payment.id).where(
                Payment.provider == provider,
                Payment.provider_txn_id == provider_txn_id,
                Payment.status != "REJECTED",
            )
        )
        is not None
    )
