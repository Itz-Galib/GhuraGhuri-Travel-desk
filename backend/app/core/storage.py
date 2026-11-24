"""Pluggable file storage port (local filesystem + S3-compatible)."""

import hashlib
import hmac
import time
import uuid
from pathlib import Path
from typing import Protocol

import boto3  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.errors import ValidationFailedError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def validate_upload(data: bytes, content_type: str | None) -> tuple[str, str]:
    """Validate file size, declared MIME type, and magic bytes. Returns (mime, ext)."""
    if not data:
        raise ValidationFailedError("Uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationFailedError("File exceeds 5 MB limit")

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME_TYPES:
        raise ValidationFailedError(f"Unsupported file type: {mime or 'unknown'}")

    # Magic-byte verification
    if mime == "image/jpeg" and not data.startswith(b"\xff\xd8\xff"):
        raise ValidationFailedError("Invalid JPEG file signature")
    if mime == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationFailedError("Invalid PNG file signature")
    if mime == "image/webp" and not (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        raise ValidationFailedError("Invalid WEBP file signature")
    if mime == "application/pdf" and not data.startswith(b"%PDF"):
        raise ValidationFailedError("Invalid PDF file signature")

    return mime, ALLOWED_MIME_TYPES[mime]


class FileStorage(Protocol):
    def put_object(self, *, bucket: str, key: str, data: bytes, content_type: str) -> str: ...
    def presigned_get_url(self, *, bucket: str, key: str, expires_seconds: int = 60) -> str: ...


class LocalFileStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def put_object(self, *, bucket: str, key: str, data: bytes, content_type: str) -> str:
        target = self.base_dir / bucket / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return key

    def presigned_get_url(self, *, bucket: str, key: str, expires_seconds: int = 60) -> str:
        settings = get_settings()
        exp = int(time.time()) + expires_seconds
        payload = f"{bucket}:{key}:{exp}".encode()
        sig = hmac.new(
            settings.jwt_secret.get_secret_value().encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return (
            f"{settings.api_v1_prefix}/admin/storage/signed"
            f"?bucket={bucket}&key={key}&exp={exp}&sig={sig}"
        )


class S3FileStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint,
            region_name=settings.storage_region,
            aws_access_key_id=(
                settings.storage_access_key.get_secret_value()
                if settings.storage_access_key
                else None
            ),
            aws_secret_access_key=(
                settings.storage_secret_key.get_secret_value()
                if settings.storage_secret_key
                else None
            ),
        )

    def put_object(self, *, bucket: str, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def presigned_get_url(self, *, bucket: str, key: str, expires_seconds: int = 60) -> str:
        return str(
            self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_seconds,
            )
        )


def get_storage() -> FileStorage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3FileStorage()
    return LocalFileStorage(settings.storage_local_dir)


def new_storage_key(prefix: str, ext: str) -> str:
    return f"{prefix}/{uuid.uuid4()}{ext}"
