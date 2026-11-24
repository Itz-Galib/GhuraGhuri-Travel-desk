"""Operator & verification schemas (spec 04 & 05)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.auth.schemas import validate_phone


class PayoutMethod(BaseModel):
    provider: Literal["BKASH", "NAGAD", "ROCKET", "BANK"]
    number: str = Field(min_length=5, max_length=32)


class OperatorProfileCreate(BaseModel):
    type: Literal["INDIVIDUAL", "GROUP"]
    display_name: str = Field(min_length=2, max_length=160)
    contact_phone: str
    facebook_url: str | None = Field(default=None, max_length=500)
    payout_methods: list[PayoutMethod] = Field(default_factory=list)

    @field_validator("contact_phone")
    @classmethod
    def phone_valid(cls, value: str) -> str:
        return validate_phone(value)


class OperatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    type: str
    display_name: str
    contact_phone: str
    facebook_url: str | None
    payout_methods: list[dict[str, str]]
    verification_status: str
    verification_note: str | None
    verified_at: datetime | None
    created_at: datetime


class VerificationDocResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operator_id: uuid.UUID
    person_name: str
    doc_type: str
    nid_last4: str | None
    created_at: datetime


class OperatorMemberInvite(BaseModel):
    identifier: str = Field(min_length=3, max_length=200)


class OperatorMemberResponse(BaseModel):
    operator_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    phone: str
    member_role: str
    created_at: datetime


class AdminOperatorDetail(BaseModel):
    operator: OperatorResponse
    documents: list[VerificationDocResponse]


class AdminDecisionRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class SignedUrlResponse(BaseModel):
    url: str
    expires_in: int = 60
