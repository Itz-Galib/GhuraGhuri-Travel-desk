"""Bookings, travellers, events, payments and idempotency (spec 03 BOOKINGS)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

ACTIVE_BOOKING_STATUSES = (
    "PENDING_PAYMENT",
    "AWAITING_VERIFICATION",
    "CONFIRMED",
    "CANCELLATION_REQUESTED",
    "COMPLETED",
)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("seats > 0", name="seats_positive"),
        CheckConstraint("source IN ('WEB','FACEBOOK','PHONE','WALK_IN')", name="source_valid"),
        CheckConstraint(
            "status IN ('PENDING_PAYMENT','AWAITING_VERIFICATION','CONFIRMED','COMPLETED',"
            "'EXPIRED','REJECTED','CANCELLATION_REQUESTED','CANCELLED',"
            "'CANCELLED_UNAVAILABLE')",
            name="status_valid",
        ),
        CheckConstraint("total_amount = unit_price * seats", name="total_matches_unit_price"),
        Index("ix_booking_user", "user_id", "created_at"),
        Index("ix_booking_departure", "departure_id", "status"),
        Index(
            "ix_booking_expiry",
            "expires_at",
            postgresql_where=text("status = 'PENDING_PAYMENT'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    departure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departures.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    contact_name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="WEB", server_default="WEB"
    )
    seats: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("offers.id"))
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    advance_required: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING_PAYMENT", server_default="PENDING_PAYMENT"
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    needs_attention: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    travellers: Mapped[list["BookingTraveller"]] = relationship(cascade="all, delete-orphan")
    events: Mapped[list["BookingEvent"]] = relationship(
        cascade="all, delete-orphan", order_by="BookingEvent.created_at"
    )
    payments: Mapped[list["Payment"]] = relationship(
        cascade="all, delete-orphan", order_by="Payment.created_at"
    )


class BookingTraveller(Base):
    __tablename__ = "booking_travellers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    age: Mapped[int | None] = mapped_column()
    gender: Mapped[str | None] = mapped_column(String(20))


class BookingEvent(Base):
    __tablename__ = "booking_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('BKASH','NAGAD','ROCKET','CASH','GATEWAY')", name="provider_valid"
        ),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status IN ('SUBMITTED','VERIFIED','REJECTED','REFUNDED')", name="status_valid"
        ),
        Index(
            "uq_txn",
            "provider",
            "provider_txn_id",
            unique=True,
            postgresql_where=text("provider_txn_id IS NOT NULL AND status <> 'REJECTED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sender_number: Mapped[str | None] = mapped_column(String(20))
    provider_txn_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SUBMITTED", server_default="SUBMITTED"
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
