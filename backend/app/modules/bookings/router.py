"""Booking & payment endpoints (spec 04)."""

import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import OperatorContext, current_operator_member, get_current_user
from app.core.errors import ValidationFailedError
from app.core.pagination import PageParams, page_of, page_params
from app.modules.bookings import repository, service
from app.modules.bookings.schemas import (
    BookingCreateRequest,
    BookingDetailResponse,
    BookingResponse,
    CancelDecisionRequest,
    CancelRequest,
    ManualBookingCreateRequest,
    PaymentResponse,
    PaymentSubmitRequest,
    PaymentVerifyRequest,
    RejectBookingRequest,
)
from app.modules.users.models import User

customer_router = APIRouter(prefix="/bookings", tags=["bookings"])
operator_router = APIRouter(prefix="/operator", tags=["operator-bookings"])


@customer_router.post("", status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    if not idempotency_key or not idempotency_key.strip():
        raise ValidationFailedError("Idempotency-Key header is required")
    return service.create_booking(
        db, user=user, idempotency_key=idempotency_key.strip(), payload=payload
    )


@customer_router.get("")
def list_my_bookings(
    pagination: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    items, total = repository.list_customer_bookings(
        db, user_id=user.id, offset=offset, limit=pagination.page_size
    )
    return page_of(
        [BookingResponse.model_validate(b) for b in items],
        total=total,
        params=pagination,
    )


@customer_router.get("/{booking_id}", response_model=BookingDetailResponse)
def get_my_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BookingDetailResponse:
    booking = repository.get_customer_booking(db, booking_id=booking_id, user_id=user.id)
    if booking is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Booking not found")
    return BookingDetailResponse.model_validate(booking)


@customer_router.post(
    "/{booking_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_payment(
    booking_id: uuid.UUID,
    payload: PaymentSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> PaymentResponse:
    payment = service.submit_payment(db, user=user, booking_id=booking_id, payload=payload)
    return PaymentResponse.model_validate(payment)


@customer_router.post("/{booking_id}/cancel-request", response_model=BookingResponse)
def request_cancellation(
    booking_id: uuid.UUID,
    payload: CancelRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BookingResponse:
    booking = service.customer_request_cancellation(
        db, user=user, booking_id=booking_id, reason=payload.reason
    )
    return BookingResponse.model_validate(booking)


@operator_router.get("/bookings")
def list_operator_bookings(
    status_filter: str | None = Query(default=None, alias="status"),
    departure_id: uuid.UUID | None = Query(default=None),
    pagination: PageParams = Depends(page_params),
    ctx: OperatorContext = Depends(current_operator_member),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    items, total = repository.list_operator_bookings(
        db,
        operator_id=ctx.operator_id,
        status_filter=status_filter,
        departure_id=departure_id,
        offset=offset,
        limit=pagination.page_size,
    )
    return page_of(
        [BookingResponse.model_validate(b) for b in items],
        total=total,
        params=pagination,
    )


@operator_router.post(
    "/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED
)
def create_manual_booking(
    payload: ManualBookingCreateRequest,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BookingResponse:
    booking = service.create_manual_booking(
        db, actor=user, operator_id=ctx.operator_id, payload=payload
    )
    return BookingResponse.model_validate(booking)


@operator_router.post("/payments/{payment_id}/verify", response_model=PaymentResponse)
def verify_payment(
    payment_id: uuid.UUID,
    payload: PaymentVerifyRequest,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> PaymentResponse:
    payment = service.operator_verify_payment(
        db,
        ctx=ctx,
        actor=user,
        payment_id=payment_id,
        approve=payload.approve,
        reason=payload.reason,
    )
    return PaymentResponse.model_validate(payment)


@operator_router.post("/bookings/{booking_id}/confirm", response_model=BookingResponse)
def confirm_booking(
    booking_id: uuid.UUID,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BookingResponse:
    booking = service.operator_confirm_or_reject_booking(
        db, ctx=ctx, actor=user, booking_id=booking_id, confirm=True, reason="Confirmed by operator"
    )
    return BookingResponse.model_validate(booking)


@operator_router.post("/bookings/{booking_id}/reject", response_model=BookingResponse)
def reject_booking(
    booking_id: uuid.UUID,
    payload: RejectBookingRequest,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BookingResponse:
    booking = service.operator_confirm_or_reject_booking(
        db, ctx=ctx, actor=user, booking_id=booking_id, confirm=False, reason=payload.reason
    )
    return BookingResponse.model_validate(booking)


@operator_router.post("/bookings/{booking_id}/cancel-decision", response_model=BookingResponse)
def cancel_decision(
    booking_id: uuid.UUID,
    payload: CancelDecisionRequest,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BookingResponse:
    booking = service.operator_decide_cancellation(
        db,
        ctx=ctx,
        actor=user,
        booking_id=booking_id,
        approve=payload.approve,
        reason=payload.reason,
    )
    return BookingResponse.model_validate(booking)


@operator_router.post("/departures/{departure_id}/cancel")
def cancel_departure(
    departure_id: uuid.UUID,
    payload: RejectBookingRequest,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, int]:
    count = service.operator_cancel_departure(
        db, ctx=ctx, actor=user, departure_id=departure_id, reason=payload.reason
    )
    return {"cancelled_bookings": count}
