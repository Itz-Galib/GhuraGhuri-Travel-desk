"""Catalog repository. Operator methods require operator_id (spec 05)."""

import uuid
from datetime import date, datetime

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.modules.operators.models import Operator
from app.modules.tours.models import Departure, Offer, TourPackage


def get_operator_tour(
    db: Session, *, operator_id: uuid.UUID, package_id: uuid.UUID
) -> TourPackage | None:
    return db.scalar(
        select(TourPackage).where(
            TourPackage.id == package_id,
            TourPackage.operator_id == operator_id,
        )
    )


def list_operator_tours(
    db: Session, *, operator_id: uuid.UUID, offset: int, limit: int
) -> tuple[list[TourPackage], int]:
    stmt = select(TourPackage).where(TourPackage.operator_id == operator_id)
    total = int(
        db.scalar(select(func.count(TourPackage.id)).where(TourPackage.operator_id == operator_id))
        or 0
    )
    items = list(
        db.scalars(stmt.order_by(TourPackage.created_at.desc()).offset(offset).limit(limit))
    )
    return items, total


def list_operator_departures(
    db: Session, *, operator_id: uuid.UUID, package_id: uuid.UUID
) -> list[Departure]:
    return list(
        db.scalars(
            select(Departure)
            .join(TourPackage, TourPackage.id == Departure.package_id)
            .where(
                TourPackage.operator_id == operator_id,
                Departure.package_id == package_id,
            )
            .order_by(Departure.start_date.asc())
        )
    )


def get_operator_departure(
    db: Session, *, operator_id: uuid.UUID, departure_id: uuid.UUID
) -> Departure | None:
    return db.scalar(
        select(Departure)
        .join(TourPackage, TourPackage.id == Departure.package_id)
        .where(
            Departure.id == departure_id,
            TourPackage.operator_id == operator_id,
        )
    )


def slug_exists(db: Session, slug: str) -> bool:
    return db.scalar(select(TourPackage.id).where(TourPackage.slug == slug)) is not None


def get_active_offers_for_packages(
    db: Session, package_ids: list[uuid.UUID], now: datetime
) -> dict[uuid.UUID, Offer]:
    if not package_ids:
        return {}
    offers = db.scalars(
        select(Offer)
        .where(
            Offer.package_id.in_(package_ids),
            Offer.is_active.is_(True),
            Offer.starts_at <= now,
            Offer.ends_at >= now,
        )
        .order_by(Offer.starts_at.desc())
    )
    result: dict[uuid.UUID, Offer] = {}
    for offer in offers:
        result.setdefault(offer.package_id, offer)
    return result


def list_public_tours(
    db: Session,
    *,
    destination: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: int | None,
    max_price: int | None,
    duration: int | None,
    q: str | None,
    sort: str | None,
    offset: int,
    limit: int,
) -> tuple[list[tuple[TourPackage, Operator]], int]:
    base = (
        select(TourPackage, Operator)
        .join(Operator, Operator.id == TourPackage.operator_id)
        .where(
            TourPackage.status == "PUBLISHED",
            Operator.verification_status == "APPROVED",
        )
    )
    if destination:
        base = base.where(TourPackage.destination.ilike(f"%{destination.strip()}%"))
    if min_price is not None:
        base = base.where(TourPackage.base_price >= min_price)
    if max_price is not None:
        base = base.where(TourPackage.base_price <= max_price)
    if duration is not None:
        base = base.where(TourPackage.duration_days == duration)
    if q:
        term = f"%{q.strip()}%"
        base = base.where(
            or_(
                TourPackage.title.ilike(term),
                TourPackage.destination.ilike(term),
                TourPackage.summary.ilike(term),
            )
        )
    if date_from is not None or date_to is not None:
        dep_sub = select(Departure.package_id).where(
            Departure.status == "OPEN",
            Departure.capacity > Departure.seats_booked,
        )
        if date_from is not None:
            dep_sub = dep_sub.where(Departure.start_date >= date_from)
        if date_to is not None:
            dep_sub = dep_sub.where(Departure.start_date <= date_to)
        base = base.where(TourPackage.id.in_(dep_sub))

    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)

    order_col: object = desc(TourPackage.created_at)
    if sort == "price_asc":
        order_col = asc(TourPackage.base_price)
    elif sort == "price_desc":
        order_col = desc(TourPackage.base_price)

    rows = db.execute(base.order_by(order_col).offset(offset).limit(limit)).all()  # type: ignore[arg-type]
    return [(r[0], r[1]) for r in rows], total


def get_public_tour_by_slug(db: Session, slug: str) -> tuple[TourPackage, Operator] | None:
    row = db.execute(
        select(TourPackage, Operator)
        .join(Operator, Operator.id == TourPackage.operator_id)
        .where(
            TourPackage.slug == slug,
            TourPackage.status == "PUBLISHED",
            Operator.verification_status == "APPROVED",
        )
    ).first()
    return (row[0], row[1]) if row else None


def list_public_departures_for_package(
    db: Session, package_id: uuid.UUID, from_date: date
) -> list[Departure]:
    return list(
        db.scalars(
            select(Departure)
            .where(
                Departure.package_id == package_id,
                Departure.status == "OPEN",
                Departure.start_date >= from_date,
            )
            .order_by(Departure.start_date.asc())
        )
    )


def search_public_departures(
    db: Session,
    *,
    target_date: date | None,
    destination: str | None,
    offset: int,
    limit: int,
) -> tuple[list[tuple[Departure, TourPackage, Operator]], int]:
    stmt = (
        select(Departure, TourPackage, Operator)
        .join(TourPackage, TourPackage.id == Departure.package_id)
        .join(Operator, Operator.id == TourPackage.operator_id)
        .where(
            TourPackage.status == "PUBLISHED",
            Operator.verification_status == "APPROVED",
            Departure.status == "OPEN",
            Departure.capacity > Departure.seats_booked,
        )
    )
    if target_date is not None:
        stmt = stmt.where(Departure.start_date == target_date)
    if destination:
        stmt = stmt.where(TourPackage.destination.ilike(f"%{destination.strip()}%"))

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.execute(stmt.order_by(Departure.start_date.asc()).offset(offset).limit(limit)).all()
    return [(r[0], r[1], r[2]) for r in rows], total


def list_public_offers(
    db: Session, now: datetime, offset: int, limit: int
) -> tuple[list[Offer], int]:
    stmt = (
        select(Offer)
        .join(TourPackage, TourPackage.id == Offer.package_id)
        .join(Operator, Operator.id == TourPackage.operator_id)
        .where(
            Offer.is_active.is_(True),
            Offer.starts_at <= now,
            Offer.ends_at >= now,
            TourPackage.status == "PUBLISHED",
            Operator.verification_status == "APPROVED",
        )
    )
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = list(db.scalars(stmt.order_by(Offer.ends_at.asc()).offset(offset).limit(limit)))
    return items, total
