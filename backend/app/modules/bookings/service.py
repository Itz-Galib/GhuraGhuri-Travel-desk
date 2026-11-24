"""Booking business logic: atomic seat reservation, idempotency, payments, cancellations."""

import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import OperatorContext
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.core.security import utcnow
from app.modules.audit.service import record_audit_log
from app.modules.bookings import repository
from app.modules.bookings.models import (
    Booking,
    BookingEvent,
    BookingTraveller,
    IdempotencyKey,
    Payment,
)
from app.modules.bookings.schemas import (
    BookingCreateRequest,
    BookingResponse,
    ManualBookingCreateRequest,
    PaymentSubmitRequest,
)
from app.modules.bookings.state import should_release_seats, validate_transition
from app.modules.notifications.service import create_notification
from app.modules.operators.models import Operator
from app.modules.tours.models import Departure, TourPackage
from app.modules.tours.repository import get_active_offers_for_packages
from app.modules.tours.service import compute_discounted_price
from app.modules.users.models import User


def _new_reference() -> str:
    return f"TB-{secrets.token_hex(3).upper()}"


def _transition(
    db: Session,
    booking: Booking,
    *,
    to_status: str,
    actor_id: uuid.UUID | None,
    note: str | None = None,
) -> None:
    from_status = booking.status
    validate_transition(from_status, to_status)
    booking.status = to_status
    if should_release_seats(from_status, to_status):
        repository.release_seats_atomic(db, departure_id=booking.departure_id, seats=booking.seats)
    db.add(
        BookingEvent(
            booking_id=booking.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            note=note,
        )
    )


def _load_bookable_departure(
    db: Session, departure_id: uuid.UUID
) -> tuple[Departure, TourPackage, Operator]:
    row = db.execute(
        select(Departure, TourPackage, Operator)
        .join(TourPackage, TourPackage.id == Departure.package_id)
        .join(Operator, Operator.id == TourPackage.operator_id)
        .where(
            Departure.id == departure_id,
            TourPackage.status == "PUBLISHED",
            Operator.verification_status == "APPROVED",
        )
    ).first()
    if row is None:
        raise NotFoundError("Departure not found or not available for booking")
    dep, pkg, op = row[0], row[1], row[2]
    if dep.status != "OPEN":
        raise ConflictError("Departure is not open for booking", code="DEPARTURE_CLOSED")
    if dep.booking_cutoff and dep.booking_cutoff <= utcnow():
        raise ConflictError("Booking cutoff has passed for this departure", code="CUTOFF_PASSED")
    return dep, pkg, op


def create_booking(
    db: Session,
    *,
    user: User,
    idempotency_key: str,
    payload: BookingCreateRequest,
) -> dict[str, Any]:
    req_hash = hashlib.sha256(
        json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    ).hexdigest()

    existing_idem = repository.get_idempotency_key(db, user_id=user.id, key=idempotency_key)
    if existing_idem is not None:
        if existing_idem.request_hash != req_hash:
            raise ConflictError(
                "Idempotency-Key reused with different request body",
                code="IDEMPOTENCY_CONFLICT",
            )
        if existing_idem.response is not None:
            return existing_idem.response

    dep, pkg, _ = _load_bookable_departure(db, payload.departure_id)

    if not repository.reserve_seats_atomic(db, departure_id=dep.id, seats=payload.seats):
        raise ConflictError("Not enough seats available", code="SEATS_UNAVAILABLE")

    now = utcnow()
    offers_map = get_active_offers_for_packages(db, [pkg.id], now)
    offer = offers_map.get(pkg.id)
    unit_price = compute_discounted_price(dep.price, offer)
    total_amount = unit_price * payload.seats
    advance_required = (total_amount * pkg.advance_percent) // 100
    expires_at = now + timedelta(minutes=get_settings().booking_hold_minutes)

    booking = Booking(
        reference=_new_reference(),
        departure_id=dep.id,
        user_id=user.id,
        contact_name=payload.contact_name.strip(),
        contact_phone=payload.contact_phone,
        source="WEB",
        seats=payload.seats,
        unit_price=unit_price,
        offer_id=offer.id if offer else None,
        total_amount=total_amount,
        advance_required=advance_required,
        status="PENDING_PAYMENT",
        expires_at=expires_at,
        notes=payload.notes,
    )
    db.add(booking)
    db.flush()

    for t in payload.travellers:
        db.add(
            BookingTraveller(
                booking_id=booking.id,
                full_name=t.full_name.strip(),
                age=t.age,
                gender=t.gender,
            )
        )
    db.add(
        BookingEvent(
            booking_id=booking.id,
            from_status=None,
            to_status="PENDING_PAYMENT",
            actor_id=user.id,
            note="Seats reserved",
        )
    )
    response_dict = BookingResponse.model_validate(booking).model_dump(mode="json")
    db.add(
        IdempotencyKey(
            user_id=user.id,
            key=idempotency_key,
            request_hash=req_hash,
            response=response_dict,
        )
    )
    db.commit()
    return response_dict


def create_manual_booking(
    db: Session,
    *,
    actor: User,
    operator_id: uuid.UUID | None,
    payload: ManualBookingCreateRequest,
) -> Booking:
    dep, pkg, _ = _load_bookable_departure(db, payload.departure_id)
    if operator_id is not None and pkg.operator_id != operator_id:
        raise NotFoundError("Departure not found")

    if not repository.reserve_seats_atomic(db, departure_id=dep.id, seats=payload.seats):
        raise ConflictError("Not enough seats available", code="SEATS_UNAVAILABLE")

    now = utcnow()
    offers_map = get_active_offers_for_packages(db, [pkg.id], now)
    offer = offers_map.get(pkg.id)
    unit_price = compute_discounted_price(dep.price, offer)
    total_amount = unit_price * payload.seats
    advance_required = (total_amount * pkg.advance_percent) // 100

    initial_status = "PENDING_PAYMENT"
    if payload.advance_paid_amount is not None:
        if payload.advance_paid_amount > total_amount:
            raise ValidationFailedError("Advance paid cannot exceed total amount")
        if payload.advance_paid_amount >= advance_required:
            initial_status = "CONFIRMED"

    booking = Booking(
        reference=_new_reference(),
        departure_id=dep.id,
        user_id=None,
        contact_name=payload.contact_name.strip(),
        contact_phone=payload.contact_phone,
        source=payload.source,
        seats=payload.seats,
        unit_price=unit_price,
        offer_id=offer.id if offer else None,
        total_amount=total_amount,
        advance_required=advance_required,
        status=initial_status,
        expires_at=(
            None
            if initial_status == "CONFIRMED"
            else now + timedelta(minutes=get_settings().booking_hold_minutes)
        ),
        needs_attention=payload.needs_attention,
        created_by=actor.id,
        notes=payload.notes,
    )
    db.add(booking)
    db.flush()

    for t in payload.travellers:
        db.add(
            BookingTraveller(
                booking_id=booking.id,
                full_name=t.full_name.strip(),
                age=t.age,
                gender=t.gender,
            )
        )
    db.add(
        BookingEvent(
            booking_id=booking.id,
            from_status=None,
            to_status=initial_status,
            actor_id=actor.id,
            note=f"Manual booking ({payload.source})",
        )
    )
    if payload.advance_paid_amount is not None:
        if payload.provider_txn_id and repository.txn_id_exists(
            db, provider=payload.payment_provider, provider_txn_id=payload.provider_txn_id
        ):
            raise ConflictError("Transaction ID already used", code="DUPLICATE_TXN_ID")
        db.add(
            Payment(
                booking_id=booking.id,
                provider=payload.payment_provider,
                amount=payload.advance_paid_amount,
                sender_number=payload.contact_phone,
                provider_txn_id=payload.provider_txn_id,
                status="VERIFIED",
                verified_by=actor.id,
                verified_at=now,
                note="Recorded with manual booking",
            )
        )
    record_audit_log(
        db,
        actor_id=actor.id,
        action="MANUAL_BOOKING_CREATED",
        entity_type="booking",
        entity_id=booking.id,
        metadata={"source": payload.source},
    )
    db.commit()
    db.refresh(booking)
    return booking


def submit_payment(
    db: Session,
    *,
    user: User,
    booking_id: uuid.UUID,
    payload: PaymentSubmitRequest,
) -> Payment:
    booking = repository.get_customer_booking(db, booking_id=booking_id, user_id=user.id)
    if booking is None:
        raise NotFoundError("Booking not found")
    if booking.status not in {"PENDING_PAYMENT", "AWAITING_VERIFICATION"}:
        raise ConflictError(
            f"Cannot submit payment in {booking.status} status", code="INVALID_STATE"
        )
    verified_sum = repository.sum_verified_payments(db, booking.id)
    if verified_sum + payload.amount > booking.total_amount:
        raise ValidationFailedError("Payment exceeds booking total amount")
    if payload.provider != "CASH":
        if not payload.provider_txn_id or not payload.provider_txn_id.strip():
            raise ValidationFailedError("provider_txn_id is required for mobile payments")
        if repository.txn_id_exists(
            db, provider=payload.provider, provider_txn_id=payload.provider_txn_id.strip()
        ):
            raise ConflictError(
                "Transaction ID has already been submitted", code="DUPLICATE_TXN_ID"
            )

    payment = Payment(
        booking_id=booking.id,
        provider=payload.provider,
        amount=payload.amount,
        sender_number=payload.sender_number,
        provider_txn_id=payload.provider_txn_id.strip() if payload.provider_txn_id else None,
        status="SUBMITTED",
    )
    db.add(payment)
    if booking.status == "PENDING_PAYMENT":
        _transition(
            db,
            booking,
            to_status="AWAITING_VERIFICATION",
            actor_id=user.id,
            note=f"Payment submitted via {payload.provider}",
        )
    db.commit()
    db.refresh(payment)
    return payment


def operator_verify_payment(
    db: Session,
    *,
    ctx: OperatorContext,
    actor: User,
    payment_id: uuid.UUID,
    approve: bool,
    reason: str | None,
) -> Payment:
    found = repository.get_operator_payment(db, operator_id=ctx.operator_id, payment_id=payment_id)
    if found is None:
        raise NotFoundError("Payment not found")
    payment, booking = found
    if payment.status != "SUBMITTED":
        raise ConflictError("Payment has already been reviewed", code="INVALID_STATE")

    now = utcnow()
    if approve:
        verified_sum = repository.sum_verified_payments(db, booking.id)
        if verified_sum + payment.amount > booking.total_amount:
            raise ConflictError("Verified payments cannot exceed booking total", code="OVERPAYMENT")
        payment.status = "VERIFIED"
        payment.verified_by = actor.id
        payment.verified_at = now
        payment.note = reason
        new_total = verified_sum + payment.amount
        if new_total >= booking.advance_required and booking.status in {
            "PENDING_PAYMENT",
            "AWAITING_VERIFICATION",
        }:
            _transition(
                db,
                booking,
                to_status="CONFIRMED",
                actor_id=actor.id,
                note="Advance payment verified",
            )
            if booking.user_id:
                create_notification(
                    db,
                    user_id=booking.user_id,
                    booking_id=booking.id,
                    title="Booking confirmed",
                    body=f"Your booking {booking.reference} has been confirmed!",
                )
    else:
        payment.status = "REJECTED"
        payment.verified_by = actor.id
        payment.verified_at = now
        payment.note = reason or "Payment rejected"
        if booking.user_id:
            create_notification(
                db,
                user_id=booking.user_id,
                booking_id=booking.id,
                title="Payment rejected",
                body=f"Payment for booking {booking.reference} was rejected: {payment.note}",
            )

    record_audit_log(
        db,
        actor_id=actor.id,
        action="PAYMENT_VERIFIED" if approve else "PAYMENT_REJECTED",
        entity_type="payment",
        entity_id=payment.id,
        metadata={"booking_id": str(booking.id)},
    )
    db.commit()
    db.refresh(payment)
    return payment


def operator_confirm_or_reject_booking(
    db: Session,
    *,
    ctx: OperatorContext,
    actor: User,
    booking_id: uuid.UUID,
    confirm: bool,
    reason: str | None,
) -> Booking:
    booking = repository.get_operator_booking(
        db, operator_id=ctx.operator_id, booking_id=booking_id
    )
    if booking is None:
        raise NotFoundError("Booking not found")
    to_status = "CONFIRMED" if confirm else "REJECTED"
    _transition(db, booking, to_status=to_status, actor_id=actor.id, note=reason)
    if booking.user_id:
        create_notification(
            db,
            user_id=booking.user_id,
            booking_id=booking.id,
            title=f"Booking {to_status.lower()}",
            body=f"Booking {booking.reference} is now {to_status}. {reason or ''}".strip(),
        )
    db.commit()
    db.refresh(booking)
    return booking


def customer_request_cancellation(
    db: Session, *, user: User, booking_id: uuid.UUID, reason: str
) -> Booking:
    booking = repository.get_customer_booking(db, booking_id=booking_id, user_id=user.id)
    if booking is None:
        raise NotFoundError("Booking not found")

    dep = db.get(Departure, booking.departure_id)
    if dep and dep.booking_cutoff and dep.booking_cutoff <= utcnow():
        raise ConflictError("Cancellation cutoff has passed", code="CUTOFF_PASSED")

    if booking.status == "PENDING_PAYMENT":
        _transition(db, booking, to_status="CANCELLED", actor_id=user.id, note=reason)
    elif booking.status == "CONFIRMED":
        _transition(db, booking, to_status="CANCELLATION_REQUESTED", actor_id=user.id, note=reason)
    else:
        raise ConflictError(
            f"Cannot request cancellation in {booking.status} status", code="INVALID_STATE"
        )
    db.commit()
    db.refresh(booking)
    return booking


def operator_decide_cancellation(
    db: Session,
    *,
    ctx: OperatorContext,
    actor: User,
    booking_id: uuid.UUID,
    approve: bool,
    reason: str | None,
) -> Booking:
    booking = repository.get_operator_booking(
        db, operator_id=ctx.operator_id, booking_id=booking_id
    )
    if booking is None:
        raise NotFoundError("Booking not found")
    if booking.status != "CANCELLATION_REQUESTED":
        raise ConflictError(
            "Booking does not have a pending cancellation request", code="INVALID_STATE"
        )
    to_status = "CANCELLED" if approve else "CONFIRMED"
    _transition(db, booking, to_status=to_status, actor_id=actor.id, note=reason)
    if booking.user_id:
        create_notification(
            db,
            user_id=booking.user_id,
            booking_id=booking.id,
            title="Cancellation request " + ("approved" if approve else "declined"),
            body=f"Your cancellation request for {booking.reference} was "
            + ("approved." if approve else f"declined: {reason or ''}"),
        )
    db.commit()
    db.refresh(booking)
    return booking


def operator_cancel_departure(
    db: Session,
    *,
    ctx: OperatorContext,
    actor: User,
    departure_id: uuid.UUID,
    reason: str,
) -> int:
    dep = db.scalar(
        select(Departure)
        .join(TourPackage, TourPackage.id == Departure.package_id)
        .where(Departure.id == departure_id, TourPackage.operator_id == ctx.operator_id)
    )
    if dep is None:
        raise NotFoundError("Departure not found")
    if dep.status == "CANCELLED":
        raise ConflictError("Departure is already cancelled", code="ALREADY_CANCELLED")

    dep.status = "CANCELLED"
    active_bookings = list(
        db.scalars(
            select(Booking).where(
                Booking.departure_id == dep.id,
                Booking.status.in_(
                    [
                        "PENDING_PAYMENT",
                        "AWAITING_VERIFICATION",
                        "CONFIRMED",
                        "CANCELLATION_REQUESTED",
                    ]
                ),
            )
        )
    )
    for b in active_bookings:
        _transition(
            db,
            b,
            to_status="CANCELLED_UNAVAILABLE",
            actor_id=actor.id,
            note=f"Departure cancelled: {reason}",
        )
        if b.user_id:
            create_notification(
                db,
                user_id=b.user_id,
                booking_id=b.id,
                title="Departure cancelled",
                body=(
                    f"Your booking {b.reference} was cancelled because the "
                    f"departure was cancelled: {reason}"
                ),
            )
    record_audit_log(
        db,
        actor_id=actor.id,
        action="DEPARTURE_BULK_CANCELLED",
        entity_type="departure",
        entity_id=dep.id,
        metadata={"cancelled_bookings": len(active_bookings), "reason": reason},
    )
    db.commit()
    return len(active_bookings)
