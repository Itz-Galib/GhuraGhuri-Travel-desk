"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime settings. Values come from env vars first, then .env files."""

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / ".env.local", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "GhuraGhuri Travel Desk API"
    environment: Literal["local", "test", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/tourdesk"
    # Neon writes DATABASE_URL_UNPOOLED; DATABASE_URL_DIRECT is our documented alias.
    database_url_unpooled: str | None = None
    database_url_direct: str | None = None
    sql_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 300

    jwt_secret: SecretStr = SecretStr("dev-only-change-me")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    refresh_cookie_name: str = "refresh_token"
    refresh_cookie_domain: str | None = None
    refresh_cookie_secure: bool = True

    cors_origins: str = "http://localhost:5173"
    rate_limit_enabled: bool = True
    internal_cron_secret: SecretStr = SecretStr("dev-cron-secret-change-me")

    booking_hold_minutes: int = 30

    nid_encryption_key: SecretStr | None = None
    nid_hash_key: SecretStr | None = None

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: Path = BACKEND_DIR / "var" / "storage"

    storage_endpoint: str | None = None
    storage_region: str | None = None
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    storage_public_bucket: str | None = None
    storage_private_bucket: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.refresh_cookie_secure and self.environment != "test"

    @property
    def migration_database_url(self) -> str:
        """Alembic must use the direct (non-pooled) Neon connection string."""
        return self.database_url_direct or self.database_url_unpooled or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
