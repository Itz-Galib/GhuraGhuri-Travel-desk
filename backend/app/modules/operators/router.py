"""Operator onboarding & admin verification endpoints (spec 04)."""

import hashlib
import hmac
import time
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db_session
from app.core.deps import OperatorContext, current_operator_member, get_admin_user, get_current_user
from app.core.errors import ForbiddenError, NotFoundError
from app.core.pagination import PageParams, page_of, page_params
from app.modules.operators import repository, service
from app.modules.operators.schemas import (
    AdminDecisionRequest,
    AdminOperatorDetail,
    OperatorMemberInvite,
    OperatorMemberResponse,
    OperatorProfileCreate,
    OperatorResponse,
    SignedUrlResponse,
    VerificationDocResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/operator", tags=["operator"])
admin_router = APIRouter(prefix="/admin", tags=["admin-operators"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/profile", response_model=OperatorResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: OperatorProfileCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OperatorResponse:
    op = service.create_operator_profile(db, user, payload)
    return OperatorResponse.model_validate(op)


@router.get("/profile", response_model=OperatorResponse)
def get_profile(
    ctx: OperatorContext = Depends(current_operator_member),
) -> OperatorResponse:
    return OperatorResponse.model_validate(ctx.operator)


@router.post(
    "/documents",
    response_model=VerificationDocResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    person_name: str = Form(..., min_length=2, max_length=160),
    doc_type: str = Form(...),
    nid_number: str | None = Form(default=None),
    file: UploadFile = File(...),
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> VerificationDocResponse:
    data = await file.read()
    doc = service.upload_verification_document(
        db,
        ctx=ctx,
        actor=user,
        person_name=person_name,
        doc_type=doc_type,
        nid_number=nid_number,
        file_bytes=data,
        content_type=file.content_type,
    )
    return VerificationDocResponse.model_validate(doc)


@router.post("/submit", response_model=OperatorResponse)
def submit_operator(
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OperatorResponse:
    op = service.submit_for_verification(db, ctx=ctx, actor=user)
    return OperatorResponse.model_validate(op)


@router.get("/members", response_model=list[OperatorMemberResponse])
def list_members(
    ctx: OperatorContext = Depends(current_operator_member),
    db: Session = Depends(get_db_session),
) -> list[OperatorMemberResponse]:
    if not ctx.is_owner:
        raise ForbiddenError("Only operator owners can view members")
    rows = repository.list_members(db, operator_id=ctx.operator_id)
    return [
        OperatorMemberResponse(
            operator_id=member.operator_id,
            user_id=member.user_id,
            full_name=member_user.full_name,
            email=member_user.email,
            phone=member_user.phone,
            member_role=member.member_role,
            created_at=member.created_at,
        )
        for member, member_user in rows
    ]


@router.post(
    "/members",
    response_model=OperatorMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    payload: OperatorMemberInvite,
    ctx: OperatorContext = Depends(current_operator_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OperatorMemberResponse:
    member, target = service.invite_staff_member(
        db, ctx=ctx, actor=user, identifier=payload.identifier
    )
    return OperatorMemberResponse(
        operator_id=member.operator_id,
        user_id=member.user_id,
        full_name=target.full_name,
        email=target.email,
        phone=target.phone,
        member_role=member.member_role,
        created_at=member.created_at,
    )


@admin_router.get("/operators")
def admin_list_operators(
    verification_status: str | None = Query(default=None),
    pagination: PageParams = Depends(page_params),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    offset = (pagination.page - 1) * pagination.page_size
    items, total = repository.list_operators_admin(
        db,
        verification_status=verification_status,
        offset=offset,
        limit=pagination.page_size,
    )
    return page_of(
        [OperatorResponse.model_validate(item) for item in items],
        total=total,
        params=pagination,
    )


@admin_router.get("/operators/{operator_id}", response_model=AdminOperatorDetail)
def admin_get_operator(
    operator_id: uuid.UUID,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> AdminOperatorDetail:
    op, docs = service.admin_get_operator_detail(db, operator_id)
    return AdminOperatorDetail(
        operator=OperatorResponse.model_validate(op),
        documents=[VerificationDocResponse.model_validate(d) for d in docs],
    )


@admin_router.get(
    "/operators/{operator_id}/documents/{doc_id}/url",
    response_model=SignedUrlResponse,
)
def admin_get_doc_url(
    operator_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> SignedUrlResponse:
    url = service.admin_issue_document_url(
        db,
        operator_id=operator_id,
        doc_id=doc_id,
        admin_user=admin,
        ip=_client_ip(request),
    )
    return SignedUrlResponse(url=url, expires_in=60)


@admin_router.post("/operators/{operator_id}/approve", response_model=OperatorResponse)
def admin_approve_operator(
    operator_id: uuid.UUID,
    request: Request,
    payload: AdminDecisionRequest | None = None,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> OperatorResponse:
    op = service.admin_decide_operator(
        db,
        operator_id=operator_id,
        decision="APPROVED",
        reason=payload.reason if payload else None,
        admin_user=admin,
        ip=_client_ip(request),
    )
    return OperatorResponse.model_validate(op)


@admin_router.post("/operators/{operator_id}/reject", response_model=OperatorResponse)
def admin_reject_operator(
    operator_id: uuid.UUID,
    payload: AdminDecisionRequest,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> OperatorResponse:
    op = service.admin_decide_operator(
        db,
        operator_id=operator_id,
        decision="REJECTED",
        reason=payload.reason,
        admin_user=admin,
        ip=_client_ip(request),
    )
    return OperatorResponse.model_validate(op)


@admin_router.post("/operators/{operator_id}/suspend", response_model=OperatorResponse)
def admin_suspend_operator(
    operator_id: uuid.UUID,
    payload: AdminDecisionRequest,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db_session),
) -> OperatorResponse:
    op = service.admin_decide_operator(
        db,
        operator_id=operator_id,
        decision="SUSPENDED",
        reason=payload.reason,
        admin_user=admin,
        ip=_client_ip(request),
    )
    return OperatorResponse.model_validate(op)


@admin_router.get("/storage/signed")
def serve_local_signed_object(
    bucket: str = Query(...),
    key: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
) -> Response:
    settings = get_settings()
    if settings.storage_backend != "local":
        raise NotFoundError("Not found")
    if exp < int(time.time()):
        raise ForbiddenError("Signed URL expired")
    expected = hmac.new(
        settings.jwt_secret.get_secret_value().encode("utf-8"),
        f"{bucket}:{key}:{exp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ForbiddenError("Invalid signature")
    target = (settings.storage_local_dir / bucket / key).resolve()
    base = (settings.storage_local_dir / bucket).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        raise NotFoundError("File not found")
    return Response(content=target.read_bytes(), media_type="application/octet-stream")
