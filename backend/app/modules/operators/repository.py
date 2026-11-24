"""Operator repository. Every operator-scoped query requires operator_id."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.operators.models import Operator, OperatorMember, VerificationDocument
from app.modules.users.models import User


def get_operator_by_id(db: Session, operator_id: uuid.UUID) -> Operator | None:
    return db.get(Operator, operator_id)


def get_operator_by_phone(db: Session, phone: str) -> Operator | None:
    return db.scalar(select(Operator).where(Operator.contact_phone == phone))


def get_membership(
    db: Session, *, operator_id: uuid.UUID, user_id: uuid.UUID
) -> OperatorMember | None:
    return db.scalar(
        select(OperatorMember).where(
            OperatorMember.operator_id == operator_id,
            OperatorMember.user_id == user_id,
        )
    )


def list_members(db: Session, *, operator_id: uuid.UUID) -> list[tuple[OperatorMember, User]]:
    rows = db.execute(
        select(OperatorMember, User)
        .join(User, User.id == OperatorMember.user_id)
        .where(OperatorMember.operator_id == operator_id)
        .order_by(OperatorMember.created_at)
    ).all()
    return [(row[0], row[1]) for row in rows]


def list_documents(db: Session, *, operator_id: uuid.UUID) -> list[VerificationDocument]:
    return list(
        db.scalars(
            select(VerificationDocument)
            .where(VerificationDocument.operator_id == operator_id)
            .order_by(VerificationDocument.created_at)
        )
    )


def get_document(
    db: Session, *, operator_id: uuid.UUID, doc_id: uuid.UUID
) -> VerificationDocument | None:
    return db.scalar(
        select(VerificationDocument).where(
            VerificationDocument.id == doc_id,
            VerificationDocument.operator_id == operator_id,
        )
    )


def get_document_by_nid_hash(db: Session, nid_hash: str) -> VerificationDocument | None:
    return db.scalar(
        select(VerificationDocument).where(
            VerificationDocument.nid_hash == nid_hash,
            VerificationDocument.doc_type == "NID_FRONT",
        )
    )


def list_operators_admin(
    db: Session,
    *,
    verification_status: str | None,
    offset: int,
    limit: int,
) -> tuple[list[Operator], int]:
    stmt = select(Operator)
    count_stmt = select(func.count(Operator.id))
    if verification_status:
        stmt = stmt.where(Operator.verification_status == verification_status)
        count_stmt = count_stmt.where(Operator.verification_status == verification_status)
    total = int(db.scalar(count_stmt) or 0)
    items = list(db.scalars(stmt.order_by(Operator.created_at.desc()).offset(offset).limit(limit)))
    return items, total
