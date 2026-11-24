"""Tour catalog: packages, images, departures, offers (spec 03 CATALOG)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TourPackage(Base):
    __tablename__ = "tour_packages"
    __table_args__ = (
        CheckConstraint("duration_days >= 1", name="duration_days_positive"),
        CheckConstraint("base_price >= 0", name="base_price_non_negative"),
        CheckConstraint("advance_percent BETWEEN 0 AND 100", name="advance_percent_range"),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','SUSPENDED','ARCHIVED')", name="status_valid"
        ),
        Index("ix_pkg_status_dest", "status", "destination"),
        Index("ix_pkg_operator", "operator_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("operators.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    destination: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    itinerary: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    inclusions: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default=text("'{}'::text[]")
    )
    exclusions: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default=text("'{}'::text[]")
    )
    duration_days: Mapped[int] = mapped_column(nullable=False)
    base_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    advance_percent: Mapped[int] = mapped_column(nullable=False, default=30)
    cancellation_policy: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="DRAFT", server_default="DRAFT"
    )
    status_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    images: Mapped[list["TourPackageImage"]] = relationship(
        back_populates="package", cascade="all, delete-orphan", order_by="TourPackageImage.position"
    )
    departures: Mapped[list["Departure"]] = relationship(back_populates="package")


class TourPackageImage(Base):
    __tablename__ = "tour_package_images"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tour_packages.id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0)

    package: Mapped[TourPackage] = relationship(back_populates="images")


class Departure(Base):
    __tablename__ = "departures"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint("seats_booked >= 0 AND seats_booked <= capacity", name="seats_range"),
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
        CheckConstraint("status IN ('OPEN','CLOSED','CANCELLED')", name="status_valid"),
        Index("ix_dep_date", "start_date", "status"),
        Index("ix_dep_package", "package_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tour_packages.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    seats_booked: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    booking_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="OPEN", server_default="OPEN"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    package: Mapped[TourPackage] = relationship(back_populates="departures")


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("discount_type IN ('PERCENT','FLAT')", name="discount_type_valid"),
        CheckConstraint("discount_value > 0", name="discount_value_positive"),
        CheckConstraint("ends_at > starts_at", name="offer_window_valid"),
        Index("ix_offer_package", "package_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tour_packages.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    discount_type: Mapped[str] = mapped_column(String(16), nullable=False)
    discount_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
