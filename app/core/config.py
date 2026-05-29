import json
from typing import Any, Literal

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

    # connection resilience — the remote Supabase pooler occasionally blips
    # (transient DNS / TCP failures) during parallel request bursts. We retry a
    # fast-failing connect a few times before surfacing a clean 503. A connect
    # *timeout* is treated as "down" and not retried (it already burned the
    # connect_args timeout — retrying would just multiply the wait).
    DB_CONNECT_MAX_RETRIES: int = 3
    DB_CONNECT_RETRY_BACKOFF_S: float = 0.25

    # connection pool sizing. The Supabase pooler does the real pooling, but our
    # own SQLAlchemy pool must have enough slots for concurrent long-held
    # connections: SSE streams (import / panel) hold one for the whole stream,
    # and the dashboard fires several claim queries in parallel. Too small a pool
    # surfaces as "QueuePool limit ... reached, connection timed out".
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_S: float = 10.0
    DB_POOL_RECYCLE_S: int = 1800

    # llm  (OpenAI-only for the hackathon — locked 2026-05-26)
    LLM_PROVIDER: Literal["openai", "fake"] = "openai"
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: SecretStr | None = None
    WHISPER_MODEL: str = "whisper-1"
    # TTS — gpt-4o-mini-tts is preferred; fall back to "tts-1" if it errors at runtime
    TTS_MODEL: str = "gpt-4o-mini-tts"
    TTS_VOICE: str = "nova"
    TTS_MAX_CHARS: int = 5000  # hard cap for the /tts endpoint
    TRANSCRIBE_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
    TRANSCRIBE_ALLOWED_MIME: list[str] = [
        "audio/webm",
        "audio/mp4",
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        "audio/x-m4a",
        "audio/mp3",
    ]

    # OCR (A1) — scanned/image documents. "none" disables → pdfplumber-only path.
    # "openai" routes image-only PDFs/images through an OpenAI vision model.
    OCR_PROVIDER: Literal["openai", "none"] = "openai"
    OCR_MODEL: str = "gpt-4o-mini"  # vision-capable; reads images + PDF file inputs

    # embeddings  (OpenAI text-embedding-3-small w/ dimensions=384 by default;
    # sentence-transformers retained as an offline fallback — see infrastructure/embeddings/)
    EMBEDDINGS_PROVIDER: Literal["openai", "sentence_transformers"] = "openai"
    EMBEDDINGS_MODEL: str = "text-embedding-3-small"
    EMBEDDINGS_DIM: int = 384
    # Max texts per embedding request when bulk-indexing narratives (rescore_all).
    # Keep below the provider's per-request input cap (OpenAI allows 2048).
    EMBEDDINGS_BATCH_SIZE: int = 256

    # vector store
    VECTOR_STORE: Literal["pgvector", "in_memory"] = "pgvector"

    # ml
    FRAUD_MODEL_PATH: str = "data/models/fraud_lgbm.txt"
    ANOMALY_MODEL_PATH: str = "data/models/anomaly_iforest.joblib"
    NEAREST_NORMAL_INDEX_PATH: str = "data/models/anomaly_knn.joblib"

    # rules
    RULES_CONFIG_PATH: str = "app/domain/rules/config.yaml"
    SIMILARITY_THRESHOLD_FS13: float = 0.85
    # Minimum cosine similarity for a neighbour to surface in the
    # "Narrativas similares" panel (and the live import SimilarityFound event).
    # Below this, a match is noise — not worth showing the analyst.
    SIMILARITY_DISPLAY_MIN: float = 0.50

    # NLP narrative analysis (entity extraction + coherence → FS-09 + summary).
    # When True, POST /claims/{id}/narrative-analysis runs the LLM analyzer once
    # per claim and caches it; FS-09's narrativa_ilogica becomes a real NLP output.
    NARRATIVE_ANALYSIS_ENABLED: bool = True

    # confidence / false-positive signalling (A2) — referential, tune via .env.
    # The model flagging high risk with NO hard rule corroborating it, or an
    # additive score straddling the verde/amarillo boundary, lowers confidence
    # and raises a "posible falso positivo" review flag (NOT an accusation).
    CONFIDENCE_ML_HIGH: float = 0.70  # ml_probability at/above this = "model says high risk"
    CONFIDENCE_VAGUE_BAND_LOW: int = 35  # additive-score lower bound of the ambiguous band
    CONFIDENCE_VAGUE_BAND_HIGH: int = 50  # additive-score upper bound of the ambiguous band

    # vehicle identity (FS-15) — decode chassis/VIN to a canonical spec and
    # compare against the declared vehicle. "hybrid" routes real VINs to NHTSA
    # vPIC and synthetic chassis to the offline deterministic registry.
    VEHICLE_DECODER_PROVIDER: Literal["hybrid", "registro", "nhtsa"] = "hybrid"
    NHTSA_VPIC_URL: str = "https://vpic.nhtsa.dot.gov/api"
    VEHICLE_DECODER_TIMEOUT_S: float = 8.0

    # agent (ReAct loop)
    MAX_REACT_STEPS: int = 3  # safety bound on tool-use iterations per query
    MAX_CONVERSATION_TURNS: int = 8  # how many HumanMessage exchanges to retain
    # Compose-phase model — defaults to LLM_DEFAULT_MODEL. Override per-machine
    # via env (e.g. COMPOSE_MODEL=gpt-4o) for faster TTFT during the demo
    # without changing default cost for everyone else. See DECISIONS.md D1.
    COMPOSE_MODEL: str | None = None

    # perf telemetry — emits one JSON log line per request with total + DB ms.
    # See app/api/middleware/perf_timing.py. Cheap (<1% overhead).
    PERF_TIMING_ENABLED: bool = True

    # data
    DATA_DIR: str = "data"
    LOAD_DATASET_ON_STARTUP: bool = True

    # storage (Supabase Storage) — re-added per user request; overrides §11/§13 deferral; OPTIONAL
    SUPABASE_URL: str | None = None
    # server-side only; NEVER exposed to the frontend
    SUPABASE_SERVICE_ROLE_KEY: SecretStr | None = None
    SUPABASE_STORAGE_BUCKET: str = "siniestros-documentos"
    UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024  # 25 MB
    UPLOAD_ALLOWED_MIME: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    ]

    # savings analysis — fraction of exposed amount recoverable when alert confirmed
    TASA_RECUPERACION_AHORRO: float = 0.6

    # auth  (V0 — local JWT, env-seeded users)
    AUTH_ENABLED: bool = True
    JWT_SECRET: SecretStr = SecretStr("change-me-before-demo")
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 480
    # JSON array of {email, password (plaintext in .env), role, full_name}.
    # Hashed with bcrypt at boot by EnvSeededUserRepo; hashes never persisted.
    AUTH_SEED_USERS: SecretStr = SecretStr("[]")

    def seed_users(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.AUTH_SEED_USERS.get_secret_value())
        except (json.JSONDecodeError, TypeError):
            return []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # §13 specifies "forbid"; kept "ignore" so a stale .env (old Supabase keys)
        # doesn't crash boot during the transition — flip to "forbid" once .env is cleaned.
        extra="ignore",
    )


settings = Settings()
