"""Password hashing, JWTs, refresh tokens and NID cryptography."""

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.core.errors import UnauthenticatedError

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy_password(password: str) -> None:
    """Burn the same time as a real verification for unknown accounts."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass


def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.access_token_minutes * 60
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("Invalid or expired access token") from exc
    if not isinstance(payload, dict) or "sub" not in payload:
        raise UnauthenticatedError("Invalid access token")
    return payload


def new_refresh_token() -> tuple[str, str]:
    plain = secrets.token_urlsafe(48)
    return plain, hash_refresh_token(plain)


def hash_refresh_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _decode_key(value: str) -> bytes:
    value = value.strip()
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        if len(decoded) == 32:
            return decoded
    except (ValueError, TypeError):
        pass
    if len(value) == 64:
        try:
            return bytes.fromhex(value)
        except ValueError:
            pass
    raise ValueError("Key must be a 32-byte base64url value or 64-char hex")


def generate_nid_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def encrypt_nid(nid: str) -> bytes:
    settings = get_settings()
    if settings.nid_encryption_key is None:
        raise RuntimeError("NID_ENCRYPTION_KEY is not configured")
    key = _decode_key(settings.nid_encryption_key.get_secret_value())
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, nid.encode("utf-8"), b"nid")


def decrypt_nid(payload: bytes) -> str:
    settings = get_settings()
    if settings.nid_encryption_key is None:
        raise RuntimeError("NID_ENCRYPTION_KEY is not configured")
    key = _decode_key(settings.nid_encryption_key.get_secret_value())
    nonce, ciphertext = payload[:12], payload[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, b"nid").decode("utf-8")


def hash_nid(nid: str) -> str:
    settings = get_settings()
    if settings.nid_hash_key is None:
        raise RuntimeError("NID_HASH_KEY is not configured")
    key = settings.nid_hash_key.get_secret_value().encode("utf-8")
    return hmac.new(key, nid.encode("utf-8"), hashlib.sha256).hexdigest()
