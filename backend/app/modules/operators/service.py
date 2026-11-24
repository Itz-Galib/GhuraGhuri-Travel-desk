"""Operator onboarding, member management, and admin verification service."""

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import encrypt_nid, hash_nid, nid_last4
from app.core.deps import OperatorContext
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.core.security import utcnow
from app.core.storage import get_storage, new_storage_key, validate_upload
from app.modules.audit.service import record_audit_log
from app.modules.auth.repository import get_user_by_identifier
from app.modules.operators import repository
from app.modules.operators.models import Operator, OperatorMember, VerificationDocument
from app.modules.operators.schemas import OperatorProfileCreate
from app.modules.users.models import User


def create_operator_profile(db: Session, user: User, payload: OperatorProfileCreate) -> Operator:
    if repository.get_operator_by_phone(db, payload.contact_phone):
        raise ConflictError(
            "An operator with this contact phone already exists",
            code="OPERATOR_PHONE_TAKEN",
        )
    existing_membership = db.query(OperatorMember).filter(OperatorMember.user_id == user.id).first()
    if existing_membership is not None:
        raise ConflictError(
            "User already belongs to an operator organisation",
            code="OPERATOR_ALREADY_EXISTS",
        )

    operator = Operator(
        kind="TOUR",
        type=payload.type,
        display_name=payload.display_name.strip(),
        contact_phone=payload.contact_phone,
        facebook_url=payload.facebook_url,
        payout_methods=[m.model_dump() for m in payload.payout_methods],
        verification_status="DRAFT",
    )
    db.add(operator)
    db.flush()

    member = OperatorMember(
        operator_id=operator.id,
        user_id=user.id,
        member_role="OWNER",
    )
    db.add(member)
    if user.role == "CUSTOMER":
        user.role = "OPERATOR"

    record_audit_log(
        db,
        actor_id=user.id,
        action="OPERATOR_CREATED",
        entity_type="operator",
        entity_id=operator.id,
    )
    db.commit()
    db.refresh(operator)
    return operator


def upload_verification_document(
    db: Session,
    *,
    ctx: OperatorContext,
    actor: User,
    person_name: str,
    doc_type: str,
    nid_number: str | None,
    file_bytes: bytes,
    content_type: str | None,
) -> VerificationDocument:
    if doc_type not in {"NID_FRONT", "NID_BACK", "SELFIE", "AUTHORIZATION_NOTE"}:
        raise ValidationFailedError("Invalid doc_type")

    mime, ext = validate_upload(file_bytes, content_type)
    nid_enc: bytes | None = None
    nid_h: str | None = None
    last4: str | None = None

    if doc_type == "NID_FRONT":
        if not nid_number or not nid_number.strip():
            raise ValidationFailedError("nid_number is required for NID_FRONT")
        try:
            nid_enc = encrypt_nid(nid_number)
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc
        nid_h = hash_nid(nid_number)
        last4 = nid_last4(nid_number)
        existing = repository.get_document_by_nid_hash(db, nid_h)
        if existing is not None and existing.operator_id != ctx.operator_id:
            raise ConflictError(
                "This NID is already registered with another operator",
                code="DUPLICATE_NID",
            )

    settings = get_settings()
    bucket = settings.storage_private_bucket or "private"
    key = new_storage_key(f"operators/{ctx.operator_id}", ext)
    get_storage().put_object(bucket=bucket, key=key, data=file_bytes, content_type=mime)

    doc = VerificationDocument(
        operator_id=ctx.operator_id,
        person_name=person_name.strip(),
        doc_type=doc_type,
        nid_encrypted=nid_enc,
        nid_hash=nid_h,
        nid_last4=last4,
        storage_key=key,
    )
    db.add(doc)
    record_audit_log(
        db,
        actor_id=actor.id,
        action="OPERATOR_DOC_UPLOADED",
        entity_type="verification_document",
        entity_id=doc.id,
        metadata={"doc_type": doc_type, "operator_id": str(ctx.operator_id)},
    )
    db.commit()
    db.refresh(doc)
    return doc


def submit_for_verification(db: Session, *, ctx: OperatorContext, actor: User) -> Operator:
    if ctx.operator.verification_status not in {"DRAFT", "REJECTED"}:
        raise ConflictError(
            f"Cannot submit operator in {ctx.operator.verification_status} status",
            code="INVALID_STATE",
        )
    docs = repository.list_documents(db, operator_id=ctx.operator_id)
    if not docs:
        raise ValidationFailedError("Upload at least one verification document before submitting")
    if not ctx.operator.payout_methods:
        raise ValidationFailedError("Add at least one payout method before submitting")

    ctx.operator.verification_status = "PENDING"
    ctx.operator.verification_note = None
    record_audit_log(
        db,
        actor_id=actor.id,
        action="OPERATOR_SUBMITTED",
        entity_type="operator",
        entity_id=ctx.operator_id,
    )
    db.commit()
    db.refresh(ctx.operator)
    return ctx.operator


def invite_staff_member(
    db: Session, *, ctx: OperatorContext, actor: User, identifier: str
) -> tuple[OperatorMember, User]:
    if not ctx.is_owner:
        raise ForbiddenError("Only operator owners can invite members")
    target = get_user_by_identifier(db, identifier)
    if target is None:
        raise NotFoundError("User not found")
    existing = repository.get_membership(db, operator_id=ctx.operator_id, user_id=target.id)
    if existing is not None:
        raise ConflictError("User is already a member of this operator", code="ALREADY_MEMBER")

    member = OperatorMember(
        operator_id=ctx.operator_id,
        user_id=target.id,
        member_role="STAFF",
    )
    db.add(member)
    if target.role == "CUSTOMER":
        target.role = "OPERATOR"

    record_audit_log(
        db,
        actor_id=actor.id,
        action="OPERATOR_MEMBER_ADDED",
        entity_type="operator",
        entity_id=ctx.operator_id,
        metadata={"member_user_id": str(target.id)},
    )
    db.commit()
    return member, target


def admin_get_operator_detail(
    db: Session, operator_id: uuid.UUID
) -> tuple[Operator, list[VerificationDocument]]:
    op = repository.get_operator_by_id(db, operator_id)
    if op is None:
        raise NotFoundError("Operator not found")
    docs = repository.list_documents(db, operator_id=operator_id)
    return op, docs


def admin_issue_document_url(
    db: Session,
    *,
    operator_id: uuid.UUID,
    doc_id: uuid.UUID,
    admin_user: User,
    ip: str | None,
) -> str:
    doc = repository.get_document(db, operator_id=operator_id, doc_id=doc_id)
    if doc is None:
        raise NotFoundError("Document not found")
    settings = get_settings()
    bucket = settings.storage_private_bucket or "private"
    url = get_storage().presigned_get_url(bucket=bucket, key=doc.storage_key, expires_seconds=60)
    record_audit_log(
        db,
        actor_id=admin_user.id,
        action="NID_VIEWED" if doc.doc_type.startswith("NID") else "DOCUMENT_VIEWED",
        entity_type="verification_document",
        entity_id=doc.id,
        metadata={"operator_id": str(operator_id), "doc_type": doc.doc_type},
        ip=ip,
    )
    db.commit()
    return url


def admin_decide_operator(
    db: Session,
    *,
    operator_id: uuid.UUID,
    decision: str,
    reason: str | None,
    admin_user: User,
    ip: str | None,
) -> Operator:
    op = repository.get_operator_by_id(db, operator_id)
    if op is None:
        raise NotFoundError("Operator not found")

    if decision == "APPROVED":
        if op.verification_status not in {"PENDING", "SUSPENDED", "REJECTED"}:
            raise ConflictError(
                "Operator cannot be approved from current status", code="INVALID_STATE"
            )
        op.verification_status = "APPROVED"
        op.verified_by = admin_user.id
        op.verified_at = utcnow()
        op.verification_note = reason
        action = "OPERATOR_APPROVED"
    elif decision == "REJECTED":
        if op.verification_status not in {"PENDING", "DRAFT"}:
            raise ConflictError(
                "Operator cannot be rejected from current status", code="INVALID_STATE"
            )
        op.verification_status = "REJECTED"
        op.verification_note = reason
        action = "OPERATOR_REJECTED"
    elif decision == "SUSPENDED":
        op.verification_status = "SUSPENDED"
        op.verification_note = reason
        action = "OPERATOR_SUSPENDED"
    else:
        raise ValidationFailedError("Invalid decision")

    record_audit_log(
        db,
        actor_id=admin_user.id,
        action=action,
        entity_type="operator",
        entity_id=op.id,
        metadata={"reason": reason or ""},
        ip=ip,
    )
    db.commit()
    db.refresh(op)
    return op
