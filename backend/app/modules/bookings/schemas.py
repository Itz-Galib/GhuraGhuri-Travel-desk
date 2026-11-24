"""Booking & payment schemas (spec 04)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.auth.schemas import validate_phone


class TravellerInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = Field(default=None, max_length=20)


class BookingCreateRequest(BaseModel):
    departure_id: uuid.UUID
    seats: int = Field(gt=0, le=50)
    contact_name: str = Field(min_length=2, max_length=160)
    contact_phone: str
    travellers: list[TravellerInput] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("contact_phone")
    @classmethod
    def phone_valid(cls, value: str) -> str:
        return validate_phone(value)


class ManualBookingCreateRequest(BaseModel):
    departure_id: uuid.UUID
    seats: int = Field(gt=0, le=50)
    contact_name: str = Field(min_length=2, max_length=160)
    contact_phone: str
    source: Literal["FACEBOOK", "PHONE", "WALK_IN"] = "FACEBOOK"
    travellers: list[TravellerInput] = Field(default_factory=list)
    advance_paid_amount: int | None = Field(default=None, gt=0)
    payment_provider: Literal["BKASH", "NAGAD", "ROCKET", "CASH"] = "BKASH"
    provider_txn_id: str | None = Field(default=None, max_length=120)
    needs_attention: bool = False
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("contact_phone")
    @classmethod
    def phone_valid(cls, value: str) -> str:
        return validate_phone(value)


class TravellerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    age: int | None
    gender: str | None


class BookingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: str | None
    to_status: str
    actor_id: uuid.UUID | None
    note: str | None
    created_at: datetime


class PaymentSubmitRequest(BaseModel):
    provider: Literal["BKASH", "NAGAD", "ROCKET", "CASH"]
    amount: int = Field(gt=0)
    sender_number: str | None = Field(default=None, max_length=20)
    provider_txn_id: str | None = Field(default=None, max_length=120)


class PaymentVerifyRequest(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=500)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    provider: str
    amount: int
    sender_number: str | None
    provider_txn_id: str | None
    status: str
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    note: str | None
    created_at: datetime


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    departure_id: uuid.UUID
    user_id: uuid.UUID | None
    contact_name: str
    contact_phone: str
    source: str
    seats: int
    unit_price: int
    offer_id: uuid.UUID | None
    total_amount: int
    advance_required: int
    status: str
    expires_at: datetime | None
    needs_attention: bool
    notes: str | None
    created_at: datetime


class BookingDetailResponse(BookingResponse):
    travellers: list[TravellerResponse] = Field(default_factory=list)
    events: list[BookingEventResponse] = Field(default_factory=list)
    payments: list[PaymentResponse] = Field(default_factory=list)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class CancelDecisionRequest(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=500)


class RejectBookingRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
