"""Catalog business logic: package CRUD, publish rules, capacity guard, pricing."""

import re
import uuid

from sqlalchemy.orm import Session

from app.core.deps import OperatorContext
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.security import utcnow
from app.modules.audit.service import record_audit_log
from app.modules.tours import repository
from app.modules.tours.models import Departure, Offer, TourPackage
from app.modules.tours.schemas import (
    DepartureCreate,
    DepartureResponse,
    DepartureUpdate,
    TourCreate,
    TourUpdate,
)
from app.modules.users.models import User


def _slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "tour"
    return base[:180]


def _unique_slug(db: Session, title: str) -> str:
    base = _slugify(title)
    candidate = base
    while repository.slug_exists(db, candidate):
        candidate = f"{base}-{uuid.uuid4().hex[:6]}"
    return candidate


def compute_discounted_price(price: int, offer: Offer | None) -> int:
    if offer is None:
        return price
    if offer.discount_type == "PERCENT":
        discounted = price - (price * offer.discount_value) // 100
    else:
        discounted = price - offer.discount_value
    return max(0, discounted)


def to_departure_response(dep: Departure, offer: Offer | None = None) -> DepartureResponse:
    return DepartureResponse(
        id=dep.id,
        package_id=dep.package_id,
        start_date=dep.start_date,
        end_date=dep.end_date,
        price=dep.price,
        effective_price=compute_discounted_price(dep.price, offer),
        capacity=dep.capacity,
        seats_booked=dep.seats_booked,
        seats_left=max(0, dep.capacity - dep.seats_booked),
        booking_cutoff=dep.booking_cutoff,
        status=dep.status,
    )


def create_tour(
    db: Session, *, ctx: OperatorContext, actor: User, payload: TourCreate
) -> TourPackage:
    pkg = TourPackage(
        operator_id=ctx.operator_id,
        title=payload.title.strip(),
        slug=_unique_slug(db, payload.title),
        destination=payload.destination.strip(),
        summary=payload.summary.strip(),
        description=payload.description.strip(),
        itinerary=payload.itinerary,
        inclusions=payload.inclusions,
        exclusions=payload.exclusions,
        duration_days=payload.duration_days,
        base_price=payload.base_price,
        advance_percent=payload.advance_percent,
        cancellation_policy=payload.cancellation_policy.strip(),
        status="DRAFT",
    )
    db.add(pkg)
    db.flush()
    record_audit_log(
        db,
        actor_id=actor.id,
        action="TOUR_CREATED",
        entity_type="tour_package",
        entity_id=pkg.id,
    )
    db.commit()
    db.refresh(pkg)
    return pkg


def get_operator_tour_or_404(
    db: Session, *, ctx: OperatorContext, package_id: uuid.UUID
) -> TourPackage:
    pkg = repository.get_operator_tour(db, operator_id=ctx.operator_id, package_id=package_id)
    if pkg is None:
        raise NotFoundError("Tour package not found")
    return pkg


def update_tour(
    db: Session,
    *,
    ctx: OperatorContext,
    actor: User,
    package_id: uuid.UUID,
    payload: TourUpdate,
) -> TourPackage:
    pkg = get_operator_tour_or_404(db, ctx=ctx, package_id=package_id)
    if pkg.status == "ARCHIVED":
        raise ConflictError("Archived packages cannot be edited", code="PACKAGE_ARCHIVED")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pkg, field, value.strip() if isinstance(value, str) else value)
    record_audit_log(
        db,
        actor_id=actor.id,
        action="TOUR_UPDATED",
        entity_type="tour_package",
        entity_id=pkg.id,
    )
    db.commit()
    db.refresh(pkg)
    return pkg


def publish_tour(
    db: Session, *, ctx: OperatorContext, actor: User, package_id: uuid.UUID
) -> TourPackage:
    if ctx.operator.verification_status != "APPROVED":
        raise ForbiddenError("Only APPROVED operators can publish packages")
    pkg = get_operator_tour_or_404(db, ctx=ctx, package_id=package_id)
    if pkg.status == "SUSPENDED":
        raise ConflictError("Suspended packages cannot be published by operator", code="SUSPENDED")
    if pkg.status == "ARCHIVED":
        raise ConflictError("Archived packages cannot be published", code="PACKAGE_ARCHIVED")
    pkg.status = "PUBLISHED"
    pkg.status_reason = None
    record_audit_log(
        db,
        actor_id=actor.id,
        action="TOUR_PUBLISHED",
        entity_type="tour_package",
        entity_id=pkg.id,
    )
    db.commit()
    db.refresh(pkg)
    return pkg


def archive_tour(
    db: Session, *, ctx: OperatorContext, actor: User, package_id: uuid.UUID
) -> TourPackage:
    pkg = get_operator_tour_or_404(db, ctx=ctx, package_id=package_id)
    pkg.status = "ARCHIVED"
    record_audit_log(
        db,
        actor_id=actor.id,
        action="TOUR_ARCHIVED",
        entity_type="tour_package",
        entity_id=pkg.id,
    )
    db.commit()
    db.refresh(pkg)
    return pkg


def create_departure(
    db: Session,
    *,
    ctx: OperatorContext,
    actor: User,
    package_id: uuid.UUID,
    payload: DepartureCreate,
) -> Departure:
    pkg = get_operator_tour_or_404(db, ctx=ctx, package_id=package_id)
    if pkg.status == "ARCHIVED":
        raise ConflictError("Cannot add departures to archived package", code="PACKAGE_ARCHIVED")
    dep = Departure(
        package_id=pkg.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        price=payload.price,
        capacity=payload.capacity,
        booking_cutoff=payload.booking_cutoff,
        status="OPEN",
    )
    db.add(dep)
    db.flush()
    record_audit_log(
        db,
        actor_id=actor.id,
        action="DEPARTURE_CREATED",
        entity_type="departure",
        entity_id=dep.id,
        metadata={"package_id": str(pkg.id)},
    )
    db.commit()
    db.refresh(dep)
    return dep


def update_departure(
    db: Session,
    *,
    ctx: OperatorContext,
    actor: User,
    departure_id: uuid.UUID,
    payload: DepartureUpdate,
) -> Departure:
    dep = repository.get_operator_departure(
        db, operator_id=ctx.operator_id, departure_id=departure_id
    )
    if dep is None:
        raise NotFoundError("Departure not found")
    if dep.status == "CANCELLED":
        raise ConflictError("Cancelled departures cannot be edited", code="DEPARTURE_CANCELLED")
    if payload.capacity is not None and payload.capacity < dep.seats_booked:
        raise ConflictError(
            f"Capacity cannot be less than seats already booked ({dep.seats_booked})",
            code="CAPACITY_BELOW_BOOKED",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(dep, field, value)
    if dep.end_date < dep.start_date:
        raise ConflictError("end_date must be on or after start_date", code="INVALID_DATES")
    record_audit_log(
        db,
        actor_id=actor.id,
        action="DEPARTURE_UPDATED",
        entity_type="departure",
        entity_id=dep.id,
    )
    db.commit()
    db.refresh(dep)
    return dep


def get_public_tour_detail(
    db: Session, slug: str
) -> tuple[TourPackage, str, list[Departure], list[Offer]]:
    found = repository.get_public_tour_by_slug(db, slug)
    if found is None:
        raise NotFoundError("Tour package not found")
    pkg, operator = found
    now = utcnow()
    departures = repository.list_public_departures_for_package(db, pkg.id, now.date())
    offers_map = repository.get_active_offers_for_packages(db, [pkg.id], now)
    offer = offers_map.get(pkg.id)
    return pkg, operator.display_name, departures, [offer] if offer else []
