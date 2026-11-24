"""Request/response schemas for auth and profile endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PHONE_PATTERN = r"^\+8801[3-9]\d{8}$"
COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "12345678",
    "123456789",
    "qwerty123",
    "iloveyou",
    "admin123",
    "letmein",
    "welcome1",
    "bangladesh",
}


def validate_phone(value: str) -> str:
    import re

    value = value.strip()
    if not re.fullmatch(PHONE_PATTERN, value):
        raise ValueError("Phone must match +8801[3-9]XXXXXXXXX")
    return value


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str
    password: str = Field(min_length=8, max_length=128)
    consent: bool
    policy_version: str = Field(default="v1", max_length=20)

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value: str) -> str:
        return validate_phone(value)

    @field_validator("consent")
    @classmethod
    def consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must accept the terms and privacy policy")
        return value

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.lower() in COMMON_PASSWORDS:
            raise ValueError("Password is too common")
        return value


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=128)


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    phone: str
    role: Literal["CUSTOMER", "OPERATOR", "ADMIN"]
    status: Literal["ACTIVE", "SUSPENDED"]
    created_at: datetime


class OperatorMembership(BaseModel):
    operator_id: uuid.UUID
    display_name: str
    member_role: str
    verification_status: str


class MeResponse(BaseModel):
    user: UserProfile
    operator_memberships: list[OperatorMembership]


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value: str | None) -> str | None:
        return validate_phone(value) if value is not None else None
