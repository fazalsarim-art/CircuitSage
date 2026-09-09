"""Typed application settings loaded once via pydantic-settings.

All configuration is read from environment variables (and the local ``.env`` file for
development). Application code must depend on :func:`get_settings` rather than reading
``os.environ`` directly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/  (this file is backend/app/core/config.py -> parents[2] == backend/)
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_version: str = "0.1.0"
    git_commit: str = "unknown"

    # PostgreSQL
    database_url: str

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "circuitsage_chunks_v1"

    # OpenAI
    openai_api_key: str = "sk-placeholder"
    openai_chat_model: str = "gpt-5.6-luna"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Auth
    jwt_secret: str
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # Application config
    frontend_origin: str = "http://localhost:5173"
    allow_registration: bool = True
    max_upload_bytes: int = 26_214_400
    max_pdf_pages: int = 300

    # Security controls (§7.12)
    security_headers_enabled: bool = True
    content_security_policy: str = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    login_rate_limit: int = 10  # attempts per window, per client IP + email
    login_rate_window_seconds: int = 60

    # Reranker
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must start with postgresql:// or postgresql+psycopg://")
        return value

    @field_validator("qdrant_url", "frontend_origin")
    @classmethod
    def _validate_http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return value

    @field_validator("embedding_dimensions", "max_pdf_pages", "max_upload_bytes")
    @classmethod
    def _validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be positive")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def psycopg_dsn(self) -> str:
        """DATABASE_URL as a plain libpq DSN (strips the SQLAlchemy ``+psycopg`` dialect)."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance (cached)."""
    return Settings()
