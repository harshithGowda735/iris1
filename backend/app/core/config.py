"""
IRIS platform configuration.

Loads settings from environment variables (or a `.env` file) with strict
validation via Pydantic-Settings. Modern asynchronous Supabase and PostgreSQL
connection variables are declared here as a single source of truth.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root application settings, validated at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database (Async SQLAlchemy + asyncpg) ────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        description="Async connection string (postgresql+asyncpg://...)",
    )

    # ── Supabase & Auth ──────────────────────────────────────
    supabase_url: str = Field(
        default="https://placeholder-project.supabase.co",
        description="Supabase project URL (https://<project-ref>.supabase.co)",
    )
    supabase_anon_key: str = Field(
        default="placeholder-anon-key",
        description="Supabase public/anon API key",
    )
    supabase_service_role_key: str = Field(
        default="placeholder-service-role-key",
        description="Supabase service role secret key (backend administrative access)",
    )
    jwt_secret: str = Field(
        default="placeholder-jwt-secret",
        validation_alias=AliasChoices("jwt_secret", "supabase_jwt_secret"),
        description="Supabase JWT secret for local token signature verification",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signature verification algorithm",
    )

    # ── Application Environment ──────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Pagination Defaults ──────────────────────────────────
    default_page_limit: int = 50
    max_page_limit: int = 200

    # ── Backwards-Compatibility Aliases ──────────────────────
    @property
    def supabase_jwt_secret(self) -> str:
        """Alias for jwt_secret to maintain compatibility with legacy references."""
        return self.jwt_secret

    @property
    def is_production(self) -> bool:
        """Return True if running in production environment."""
        return self.app_env == "production"

    # ── Validators ───────────────────────────────────────────
    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """Ensure the database URL uses the asyncpg driver.

        Converts raw 'postgres://' or 'postgresql://' URLs copied from
        the Supabase dashboard into 'postgresql+asyncpg://'.
        """
        if isinstance(v, str):
            cleaned = v.strip()
            if cleaned.startswith("postgres://"):
                return cleaned.replace("postgres://", "postgresql+asyncpg://", 1)
            if cleaned.startswith("postgresql://") and not cleaned.startswith("postgresql+asyncpg://"):
                return cleaned.replace("postgresql://", "postgresql+asyncpg://", 1)
            return cleaned
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Accept both a JSON-encoded string and a native list for CORS origins."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                # Comma-separated fallback
                return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


# Module-level singleton — import this everywhere.
settings = Settings()
