"""Sensitive field encryption and hashing utilities (spec 05 Sensitive data)."""

import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def _encryption_key() -> bytes:
    raw = get_settings().nid_encryption_key
    secret = raw.get_secret_value() if raw else ""
    if not secret:
        # Dev-only deterministic key; prod must configure NID_ENCRYPTION_KEY.
        return hashlib.sha256(b"dev-nid-encryption-key").digest()
    try:
        decoded = bytes.fromhex(secret)
        if len(decoded) == 32:
            return decoded
    except ValueError:
        pass
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _hash_key() -> bytes:
    raw = get_settings().nid_hash_key
    secret = raw.get_secret_value() if raw else "dev-nid-hash-key"
    return secret.encode("utf-8")


def normalize_nid(nid: str) -> str:
    return "".join(ch for ch in nid.strip() if ch.isdigit())


def encrypt_nid(nid: str) -> bytes:
    """Encrypt normalized NID using AES-256-GCM (nonce || ciphertext)."""
    normalized = normalize_nid(nid)
    if len(normalized) not in (10, 13, 17):
        raise ValueError("Bangladesh NID must be 10, 13, or 17 digits")
    nonce = os.urandom(12)
    aesgcm = AESGCM(_encryption_key())
    ct = aesgcm.encrypt(nonce, normalized.encode("utf-8"), None)
    return nonce + ct


def decrypt_nid(blob: bytes) -> str:
    """Decrypt AES-256-GCM encrypted NID."""
    nonce, ct = blob[:12], blob[12:]
    aesgcm = AESGCM(_encryption_key())
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")


def hash_nid(nid: str) -> str:
    """Keyed HMAC-SHA256 for duplicate NID detection."""
    normalized = normalize_nid(nid)
    return hmac.new(_hash_key(), normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def nid_last4(nid: str) -> str:
    normalized = normalize_nid(nid)
    return normalized[-4:]
