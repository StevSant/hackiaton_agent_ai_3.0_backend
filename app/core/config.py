from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # app
    APP_ENV: Literal["dev", "test", "prod"] = "dev"
    APP_NAME: str = "hackiaton-agent-ai-3-0-backend"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    DEBUG_ENABLED: bool = True  # gates PATCH /claims/{id} fire-test endpoint

    API_V1_PREFIX: str = "/api/v1"
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:4200"]

    # uvicorn server (consumed by `uv run app` entrypoint in app/cli.py)
    SERVER_HOST: str = "0.0.0.0"  # noqa: S104  bind-all is intentional for docker/dev
    SERVER_PORT: int = 8000
    SERVER_RELOAD: bool = True

    # database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    @property
    def DATABASE_URL_RAW(self) -> str:
        # raw asyncpg form for bulk COPY in load_dataset (strip the +asyncpg suffix)
        return self.DATABASE_URL.replace("+asyncpg", "")

    # llm  (OpenAI-only for the hackathon — locked 2026-05-26)
    LLM_PROVIDER: Literal["openai", "fake"] = "openai"
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: SecretStr | None = None

    # embeddings  (OpenAI text-embedding-3-small w/ dimensions=384 by default;
    # sentence-transformers retained as an offline fallback — see infrastructure/embeddings/)
    EMBEDDINGS_PROVIDER: Literal["openai", "sentence_transformers"] = "openai"
    EMBEDDINGS_MODEL: str = "text-embedding-3-small"
    EMBEDDINGS_DIM: int = 384

    # vector store
    VECTOR_STORE: Literal["pgvector", "in_memory"] = "pgvector"

    # ml
    FRAUD_MODEL_PATH: str = "data/models/fraud_lgbm.txt"
    ANOMALY_MODEL_PATH: str = "data/models/anomaly_iforest.joblib"

    # rules
    RULES_CONFIG_PATH: str = "app/domain/rules/config.yaml"
    SIMILARITY_THRESHOLD_FS13: float = 0.85

    # agent (ReAct loop)
    MAX_REACT_STEPS: int = 3  # safety bound on tool-use iterations per query
    MAX_CONVERSATION_TURNS: int = 8  # how many HumanMessage exchanges to retain

    # data
    DATA_DIR: str = "data"
    LOAD_DATASET_ON_STARTUP: bool = True

    # auth  (V0 — local JWT, env-seeded users)
    AUTH_ENABLED: bool = True
    JWT_SECRET: SecretStr = SecretStr("change-me-before-demo")
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 480
    # JSON array of {email, password (plaintext in .env), role, full_name}.
    # Hashed with bcrypt at boot by EnvSeededUserRepo; hashes never persisted.
    AUTH_SEED_USERS: SecretStr = SecretStr("[]")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # §13 specifies "forbid"; kept "ignore" so a stale .env (old Supabase keys)
        # doesn't crash boot during the transition — flip to "forbid" once .env is cleaned.
        extra="ignore",
    )


settings = Settings()
