from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: Literal["dev", "test", "prod"] = "dev"
    APP_NAME: str = "hackiaton-agent-ai-3-0-backend"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    API_V1_PREFIX: str = "/api/v1"
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:4200"]

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: SecretStr | None = None
    SUPABASE_SERVICE_ROLE_KEY: SecretStr | None = None
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWKS_URL: str | None = None

    LLM_PROVIDER: Literal["openai", "anthropic", "local"] = "openai"
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None

    EMBEDDINGS_PROVIDER: Literal["openai"] = "openai"
    EMBEDDINGS_MODEL: str = "text-embedding-3-small"
    EMBEDDINGS_DIM: int = 1536

    UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024
    UPLOAD_ALLOWED_MIME: list[str] = [
        "application/pdf",
        "text/plain",
        "text/markdown",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
