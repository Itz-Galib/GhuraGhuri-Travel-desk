"""Operators, members and verification documents (spec 03 OPERATORS)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Operator(Base):
    __tablename__ = "operators"
    __table_args__ = (
        CheckConstraint("kind IN ('TOUR')", name="kind_valid"),
        CheckConstraint("type IN ('INDIVIDUAL','GROUP')", name="type_valid"),
        CheckConstraint(
            "verification_status IN ('DRAFT','PENDING','APPROVED','REJECTED','SUSPENDED')",
            name="verification_status_valid",
        ),
        CheckConstraint("commission_bps BETWEEN 0 AND 10000", name="commission_bps_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="TOUR")
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    facebook_url: Mapped[str | None] = mapped_column(String(500))
    payout_methods: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    commission_bps: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    verification_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="DRAFT", server_default="DRAFT"
    )
    verification_note: Mapped[str | None] = mapped_column(Text)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OperatorMember(Base):
    __tablename__ = "operator_members"
    __table_args__ = (
        CheckConstraint("member_role IN ('OWNER','STAFF')", name="member_role_valid"),
        Index(
            "one_owner_per_operator",
            "operator_id",
            unique=True,
            postgresql_where=text("member_role = 'OWNER'"),
        ),
    )

    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("operators.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    member_role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class VerificationDocument(Base):
    __tablename__ = "verification_documents"
    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('NID_FRONT','NID_BACK','SELFIE','AUTHORIZATION_NOTE')",
            name="doc_type_valid",
        ),
        Index(
            "uq_nid_hash",
            "nid_hash",
            unique=True,
            postgresql_where=text("nid_hash IS NOT NULL AND doc_type = 'NID_FRONT'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("operators.id"), nullable=False)
    person_name: Mapped[str] = mapped_column(String(160), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    nid_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    nid_hash: Mapped[str | None] = mapped_column(Text)
    nid_last4: Mapped[str | None] = mapped_column(String(4))
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
