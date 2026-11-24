"""Catalog schemas: packages, departures, offers (spec 04)."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TourCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    destination: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=5, max_length=400)
    description: str = Field(min_length=10, max_length=10000)
    itinerary: list[dict[str, Any]] = Field(default_factory=list)
    inclusions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    duration_days: int = Field(ge=1, le=60)
    base_price: int = Field(ge=0)
    advance_percent: int = Field(default=30, ge=0, le=100)
    cancellation_policy: str = Field(min_length=3, max_length=2000)


class TourUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    destination: str | None = Field(default=None, min_length=2, max_length=120)
    summary: str | None = Field(default=None, min_length=5, max_length=400)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    itinerary: list[dict[str, Any]] | None = None
    inclusions: list[str] | None = None
    exclusions: list[str] | None = None
    duration_days: int | None = Field(default=None, ge=1, le=60)
    base_price: int | None = Field(default=None, ge=0)
    advance_percent: int | None = Field(default=None, ge=0, le=100)
    cancellation_policy: str | None = Field(default=None, min_length=3, max_length=2000)


class DepartureCreate(BaseModel):
    start_date: date
    end_date: date
    price: int = Field(ge=0)
    capacity: int = Field(gt=0, le=500)
    booking_cutoff: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "DepartureCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class DepartureUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    price: int | None = Field(default=None, ge=0)
    capacity: int | None = Field(default=None, gt=0, le=500)
    booking_cutoff: datetime | None = None
    status: Literal["OPEN", "CLOSED"] | None = None


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    package_id: uuid.UUID
    title: str
    discount_type: Literal["PERCENT", "FLAT"]
    discount_value: int
    starts_at: datetime
    ends_at: datetime
    is_active: bool


class DepartureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    package_id: uuid.UUID
    start_date: date
    end_date: date
    price: int
    effective_price: int | None = None
    capacity: int
    seats_booked: int
    seats_left: int = 0
    booking_cutoff: datetime | None
    status: str


class TourPackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operator_id: uuid.UUID
    title: str
    slug: str
    destination: str
    summary: str
    description: str
    itinerary: list[dict[str, Any]]
    inclusions: list[str]
    exclusions: list[str]
    duration_days: int
    base_price: int
    advance_percent: int
    cancellation_policy: str
    status: str
    status_reason: str | None
    created_at: datetime


class PublicTourSummary(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    destination: str
    summary: str
    duration_days: int
    base_price: int
    discounted_price: int
    operator_name: str
    operator_verified: bool
    active_offer: OfferResponse | None = None


class PublicTourDetail(BaseModel):
    package: TourPackageResponse
    operator_name: str
    operator_verified: bool
    departures: list[DepartureResponse]
    active_offers: list[OfferResponse]


class PublicDepartureSearchItem(BaseModel):
    departure: DepartureResponse
    package_id: uuid.UUID
    package_title: str
    package_slug: str
    destination: str
    duration_days: int
    operator_name: str
    discounted_price: int
