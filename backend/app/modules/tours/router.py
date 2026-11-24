"""Catalog endpoints: operator CRUD & public discovery (spec 04)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import OperatorContext, current_operator_member, get_current_user
from app.core.pagination import PageParams, page_of, page_params
from app.core.security import utcnow
from app.modules.tours import repository, service
from app.modules.tours.schemas import (
    DepartureCreate,
    DepartureResponse,
    DepartureUpdate,
    OfferResponse,
    PublicDepartureSearchItem,
    PublicTourDetail,
    PublicTourSummary,
    TourCreate,
    TourPackageResponse,
    TourUpdate,
)
from app.modules.users.models import User

public_router = APIRouter(tags=["catalog"])
operator_router = APIRouter(prefix="/operator", tags=["operator-catalog"])


@operator_router.get("/tours")
def list_operator_tours(
    pagination: PageParams = Depends(page_params),
    ctx: OperatorContext = Depends(current_operator_member),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    items, total = repository.list_operator_tours(
        db, operator_id=ctx.operator_id, offset=offset, limit=pagination.page_size
    )
    return page_of(
        [TourPackageResponse.model_validate(item) for item in items],
        total=total,
        params=pagination,
    )


@operator_router.post(
    "/tours", response_model=TourPackageResponse, status_code=status.HTTP_201_CREATED
)
def create_tour(
    payload: TourCreate,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TourPackageResponse:
    pkg = service.create_tour(db, ctx=ctx, actor=user, payload=payload)
    return TourPackageResponse.model_validate(pkg)


@operator_router.get("/tours/{package_id}", response_model=TourPackageResponse)
def get_operator_tour(
    package_id: uuid.UUID,
    ctx: OperatorContext = Depends(current_operator_member),
    db: Session = Depends(get_db_session),
) -> TourPackageResponse:
    pkg = service.get_operator_tour_or_404(db, ctx=ctx, package_id=package_id)
    return TourPackageResponse.model_validate(pkg)


@operator_router.patch("/tours/{package_id}", response_model=TourPackageResponse)
def update_operator_tour(
    package_id: uuid.UUID,
    payload: TourUpdate,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TourPackageResponse:
    pkg = service.update_tour(db, ctx=ctx, actor=user, package_id=package_id, payload=payload)
    return TourPackageResponse.model_validate(pkg)


@operator_router.post("/tours/{package_id}/publish", response_model=TourPackageResponse)
def publish_tour(
    package_id: uuid.UUID,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TourPackageResponse:
    pkg = service.publish_tour(db, ctx=ctx, actor=user, package_id=package_id)
    return TourPackageResponse.model_validate(pkg)


@operator_router.post("/tours/{package_id}/archive", response_model=TourPackageResponse)
def archive_tour(
    package_id: uuid.UUID,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TourPackageResponse:
    pkg = service.archive_tour(db, ctx=ctx, actor=user, package_id=package_id)
    return TourPackageResponse.model_validate(pkg)


@operator_router.get("/tours/{package_id}/departures", response_model=list[DepartureResponse])
def list_operator_departures(
    package_id: uuid.UUID,
    ctx: OperatorContext = Depends(current_operator_member),
    db: Session = Depends(get_db_session),
) -> list[DepartureResponse]:
    service.get_operator_tour_or_404(db, ctx=ctx, package_id=package_id)
    deps = repository.list_operator_departures(
        db, operator_id=ctx.operator_id, package_id=package_id
    )
    return [service.to_departure_response(d) for d in deps]


@operator_router.post(
    "/tours/{package_id}/departures",
    response_model=DepartureResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_departure(
    package_id: uuid.UUID,
    payload: DepartureCreate,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DepartureResponse:
    dep = service.create_departure(db, ctx=ctx, actor=user, package_id=package_id, payload=payload)
    return service.to_departure_response(dep)


@operator_router.patch("/departures/{departure_id}", response_model=DepartureResponse)
def update_departure(
    departure_id: uuid.UUID,
    payload: DepartureUpdate,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DepartureResponse:
    dep = service.update_departure(
        db, ctx=ctx, actor=user, departure_id=departure_id, payload=payload
    )
    return service.to_departure_response(dep)


@public_router.get("/tours")
def list_public_tours(
    destination: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    duration: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    pagination: PageParams = Depends(page_params),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    rows, total = repository.list_public_tours(
        db,
        destination=destination,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
        duration=duration,
        q=q,
        sort=sort,
        offset=offset,
        limit=pagination.page_size,
    )
    offers_map = repository.get_active_offers_for_packages(
        db, [pkg.id for pkg, _ in rows], utcnow()
    )
    items = []
    for pkg, op in rows:
        offer = offers_map.get(pkg.id)
        items.append(
            PublicTourSummary(
                id=pkg.id,
                title=pkg.title,
                slug=pkg.slug,
                destination=pkg.destination,
                summary=pkg.summary,
                duration_days=pkg.duration_days,
                base_price=pkg.base_price,
                discounted_price=service.compute_discounted_price(pkg.base_price, offer),
                operator_name=op.display_name,
                operator_verified=op.verification_status == "APPROVED",
                active_offer=OfferResponse.model_validate(offer) if offer else None,
            )
        )
    return page_of(items, total=total, params=pagination)


@public_router.get("/tours/{slug}", response_model=PublicTourDetail)
def get_public_tour(slug: str, db: Session = Depends(get_db_session)) -> PublicTourDetail:
    pkg, op_name, deps, offers = service.get_public_tour_detail(db, slug)
    active_offer = offers[0] if offers else None
    return PublicTourDetail(
        package=TourPackageResponse.model_validate(pkg),
        operator_name=op_name,
        operator_verified=True,
        departures=[service.to_departure_response(d, active_offer) for d in deps],
        active_offers=[OfferResponse.model_validate(o) for o in offers],
    )


@public_router.get("/departures")
def search_public_departures(
    date_param: date | None = Query(default=None, alias="date"),
    destination: str | None = Query(default=None),
    pagination: PageParams = Depends(page_params),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    rows, total = repository.search_public_departures(
        db,
        target_date=date_param,
        destination=destination,
        offset=offset,
        limit=pagination.page_size,
    )
    offers_map = repository.get_active_offers_for_packages(
        db, [pkg.id for _, pkg, _ in rows], utcnow()
    )
    items = []
    for dep, pkg, op in rows:
        offer = offers_map.get(pkg.id)
        dep_resp = service.to_departure_response(dep, offer)
        items.append(
            PublicDepartureSearchItem(
                departure=dep_resp,
                package_id=pkg.id,
                package_title=pkg.title,
                package_slug=pkg.slug,
                destination=pkg.destination,
                duration_days=pkg.duration_days,
                operator_name=op.display_name,
                discounted_price=dep_resp.effective_price or dep.price,
            )
        )
    return page_of(items, total=total, params=pagination)


@public_router.get("/offers")
def list_public_offers(
    pagination: PageParams = Depends(page_params),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    offers, total = repository.list_public_offers(
        db, utcnow(), offset=offset, limit=pagination.page_size
    )
    return page_of(
        [OfferResponse.model_validate(o) for o in offers],
        total=total,
        params=pagination,
    )
