"""Admin & operator dashboard endpoints (spec 04 & Phase 5)."""

import csv
import io
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import OperatorContext, current_operator_member, get_admin_user
from app.core.errors import ConflictError, NotFoundError
from app.core.pagination import PageParams, page_of, page_params
from app.core.security import utcnow
from app.modules.audit.models import AuditLog
from app.modules.audit.service import record_audit_log
from app.modules.bookings import service as booking_service
from app.modules.bookings.models import Booking, Payment
from app.modules.bookings.schemas import BookingResponse, ManualBookingCreateRequest
from app.modules.bookings.service import _transition
from app.modules.notifications.service import (
    build_unavailable_whatsapp_message,
    create_notification,
)
from app.modules.operators.models import Operator
from app.modules.tours.models import Departure, Offer, TourPackage
from app.modules.tours.schemas import OfferResponse, TourPackageResponse
from app.modules.users.models import User

admin_router = APIRouter(prefix="/admin", tags=["admin"])
operator_dash_router = APIRouter(prefix="/operator", tags=["operator-dashboard"])


class ReasonBody(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class FlagBody(BaseModel):
    needs_attention: bool


class OfferCreateRequest(BaseModel):
    package_id: uuid.UUID
    title: str = Field(min_length=2, max_length=160)
    discount_type: Literal["PERCENT", "FLAT"]
    discount_value: int = Field(gt=0)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def check_window(self) -> "OfferCreateRequest":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.discount_type == "PERCENT" and self.discount_value > 100:
            raise ValueError("PERCENT discount cannot exceed 100")
        return self


class OfferUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    is_active: bool | None = None
    ends_at: datetime | None = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    meta: dict[str, object]
    created_at: datetime


@operator_dash_router.get("/dashboard")
def operator_dashboard(
    ctx: OperatorContext = Depends(current_operator_member),
    db: Session = Depends(get_db_session),
) -> dict[str, int]:
    today = utcnow().date()
    packages_count = int(
        db.scalar(
            select(func.count(TourPackage.id)).where(
                TourPackage.operator_id == ctx.operator_id,
                TourPackage.status != "ARCHIVED",
            )
        )
        or 0
    )
    upcoming_departures = int(
        db.scalar(
            select(func.count(Departure.id))
            .join(TourPackage, TourPackage.id == Departure.package_id)
            .where(
                TourPackage.operator_id == ctx.operator_id,
                Departure.status == "OPEN",
                Departure.start_date >= today,
            )
        )
        or 0
    )
    seats_sold = int(
        db.scalar(
            select(func.coalesce(func.sum(Departure.seats_booked), 0))
            .join(TourPackage, TourPackage.id == Departure.package_id)
            .where(TourPackage.operator_id == ctx.operator_id)
        )
        or 0
    )
    pending_verifications = int(
        db.scalar(
            select(func.count(Payment.id))
            .join(Booking, Booking.id == Payment.booking_id)
            .join(Departure, Departure.id == Booking.departure_id)
            .join(TourPackage, TourPackage.id == Departure.package_id)
            .where(TourPackage.operator_id == ctx.operator_id, Payment.status == "SUBMITTED")
        )
        or 0
    )
    return {
        "packages_count": packages_count,
        "upcoming_departures": upcoming_departures,
        "seats_sold": seats_sold,
        "pending_verifications": pending_verifications,
    }


@admin_router.get("/dashboard")
def admin_dashboard(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    pending_operators = int(
        db.scalar(select(func.count(Operator.id)).where(Operator.verification_status == "PENDING"))
        or 0
    )
    needs_attention = int(
        db.scalar(select(func.count(Booking.id)).where(Booking.needs_attention.is_(True))) or 0
    )
    revenue_booked = int(
        db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "VERIFIED")
        )
        or 0
    )
    status_rows = db.execute(
        select(Booking.status, func.count(Booking.id)).group_by(Booking.status)
    ).all()
    return {
        "pending_operators": pending_operators,
        "needs_attention": needs_attention,
        "revenue_booked": revenue_booked,
        "bookings_by_status": {row[0]: int(row[1]) for row in status_rows},
    }


@admin_router.get("/bookings", response_model=None)
def admin_list_bookings(
    status_filter: str | None = Query(default=None, alias="status"),
    source: str | None = Query(default=None),
    format: str | None = Query(default=None),
    pagination: PageParams = Depends(page_params),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object] | Response:
    stmt = select(Booking)
    if status_filter:
        stmt = stmt.where(Booking.status == status_filter)
    if source:
        stmt = stmt.where(Booking.source == source)

    if format == "csv":
        rows = list(db.scalars(stmt.order_by(Booking.created_at.desc()).limit(1000)))
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "reference",
                "contact_name",
                "contact_phone",
                "source",
                "seats",
                "total_amount",
                "status",
                "needs_attention",
                "created_at",
            ]
        )
        for b in rows:
            writer.writerow(
                [
                    str(b.id),
                    b.reference,
                    b.contact_name,
                    b.contact_phone,
                    b.source,
                    b.seats,
                    b.total_amount,
                    b.status,
                    b.needs_attention,
                    b.created_at.isoformat(),
                ]
            )
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=bookings.csv"},
        )

    offset = (pagination.page - 1) * pagination.page_size
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = list(
        db.scalars(
            stmt.order_by(Booking.created_at.desc()).offset(offset).limit(pagination.page_size)
        )
    )
    return page_of(
        [BookingResponse.model_validate(b) for b in items],
        total=total,
        params=pagination,
    )


@admin_router.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def admin_create_manual_booking(
    payload: ManualBookingCreateRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> BookingResponse:
    booking = booking_service.create_manual_booking(
        db, actor=admin, operator_id=None, payload=payload
    )
    return BookingResponse.model_validate(booking)


@admin_router.post("/bookings/{booking_id}/notify-unavailable")
def admin_notify_unavailable(
    booking_id: uuid.UUID,
    payload: ReasonBody,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found")
    dep = db.get(Departure, booking.departure_id)
    pkg = db.get(TourPackage, dep.package_id) if dep else None
    package_title = pkg.title if pkg else "Tour Package"

    _transition(
        db,
        booking,
        to_status="CANCELLED_UNAVAILABLE",
        actor_id=admin.id,
        note=payload.reason,
    )
    message_text, whatsapp_url = build_unavailable_whatsapp_message(
        reference=booking.reference,
        contact_name=booking.contact_name,
        contact_phone=booking.contact_phone,
        package_title=package_title,
        reason=payload.reason,
    )
    create_notification(
        db,
        user_id=booking.user_id,
        booking_id=booking.id,
        channel="IN_APP" if booking.user_id else "MANUAL_MESSAGE",
        title="Tour unavailable",
        body=message_text,
    )
    record_audit_log(
        db,
        actor_id=admin.id,
        action="BOOKING_NOTIFY_UNAVAILABLE",
        entity_type="booking",
        entity_id=booking.id,
        metadata={"reason": payload.reason},
    )
    db.commit()
    return {
        "booking_id": str(booking.id),
        "status": booking.status,
        "message_text": message_text,
        "whatsapp_url": whatsapp_url,
    }


@admin_router.post("/bookings/{booking_id}/flag", response_model=BookingResponse)
def admin_flag_booking(
    booking_id: uuid.UUID,
    payload: FlagBody,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> BookingResponse:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found")
    booking.needs_attention = payload.needs_attention
    record_audit_log(
        db,
        actor_id=admin.id,
        action="BOOKING_FLAGGED",
        entity_type="booking",
        entity_id=booking.id,
        metadata={"needs_attention": payload.needs_attention},
    )
    db.commit()
    db.refresh(booking)
    return BookingResponse.model_validate(booking)


@admin_router.post("/tours/{package_id}/suspend", response_model=TourPackageResponse)
def admin_suspend_tour(
    package_id: uuid.UUID,
    payload: ReasonBody,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> TourPackageResponse:
    pkg = db.get(TourPackage, package_id)
    if pkg is None:
        raise NotFoundError("Tour package not found")
    pkg.status = "SUSPENDED"
    pkg.status_reason = payload.reason
    record_audit_log(
        db,
        actor_id=admin.id,
        action="TOUR_SUSPENDED",
        entity_type="tour_package",
        entity_id=pkg.id,
        metadata={"reason": payload.reason},
    )
    db.commit()
    db.refresh(pkg)
    return TourPackageResponse.model_validate(pkg)


@admin_router.post("/tours/{package_id}/unsuspend", response_model=TourPackageResponse)
def admin_unsuspend_tour(
    package_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> TourPackageResponse:
    pkg = db.get(TourPackage, package_id)
    if pkg is None:
        raise NotFoundError("Tour package not found")
    if pkg.status != "SUSPENDED":
        raise ConflictError("Tour is not suspended", code="INVALID_STATE")
    pkg.status = "PUBLISHED"
    pkg.status_reason = None
    record_audit_log(
        db,
        actor_id=admin.id,
        action="TOUR_UNSUSPENDED",
        entity_type="tour_package",
        entity_id=pkg.id,
    )
    db.commit()
    db.refresh(pkg)
    return TourPackageResponse.model_validate(pkg)


@admin_router.get("/offers")
def admin_list_offers(
    pagination: PageParams = Depends(page_params),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    total = int(db.scalar(select(func.count(Offer.id))) or 0)
    items = list(
        db.scalars(
            select(Offer)
            .order_by(Offer.starts_at.desc())
            .offset(offset)
            .limit(pagination.page_size)
        )
    )
    return page_of(
        [OfferResponse.model_validate(o) for o in items],
        total=total,
        params=pagination,
    )


@admin_router.post("/offers", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
def admin_create_offer(
    payload: OfferCreateRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> OfferResponse:
    pkg = db.get(TourPackage, payload.package_id)
    if pkg is None:
        raise NotFoundError("Tour package not found")
    offer = Offer(
        package_id=pkg.id,
        title=payload.title.strip(),
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=True,
        created_by=admin.id,
    )
    db.add(offer)
    db.flush()
    record_audit_log(
        db,
        actor_id=admin.id,
        action="OFFER_CREATED",
        entity_type="offer",
        entity_id=offer.id,
    )
    db.commit()
    db.refresh(offer)
    return OfferResponse.model_validate(offer)


@admin_router.patch("/offers/{offer_id}", response_model=OfferResponse)
def admin_update_offer(
    offer_id: uuid.UUID,
    payload: OfferUpdateRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> OfferResponse:
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise NotFoundError("Offer not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(offer, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(offer)
    return OfferResponse.model_validate(offer)


@admin_router.get("/audit-logs")
def admin_list_audit_logs(
    pagination: PageParams = Depends(page_params),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    total = int(db.scalar(select(func.count(AuditLog.id))) or 0)
    items = list(
        db.scalars(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(pagination.page_size)
        )
    )
    return page_of(
        [AuditLogResponse.model_validate(a) for a in items],
        total=total,
        params=pagination,
    )
