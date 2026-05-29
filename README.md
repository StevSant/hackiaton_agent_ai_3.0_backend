# hackiaton_agent_ai_3.0_backend

Backend FastAPI + LangGraph de **Centinela IA** — detector de posibles fraudes en siniestros para el reto Aseguradora del Sur (hackIAthon 2026). Ver [`CLAUDE.md`](./CLAUDE.md) para las convenciones de desarrollo.

> El sistema **alerta, no acusa**. Toda salida es una recomendación para revisión humana.

## Prerrequisitos

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (gestor de paquetes — obligatorio, nunca `pip`)
- Docker + Docker Compose (para la instancia local de Postgres + pgvector)

## Configuración

```bash
uv sync                          # instala dependencias desde el lockfile
cp .env.example .env             # rellenar valores reales (al menos OPENAI_API_KEY)
```

## Ejecutar

```bash
docker compose up -d db          # levanta Postgres+pgvector local
uv run alembic upgrade head      # aplica migraciones
uv run python scripts/generate_dataset.py   # genera el dataset sintético (determinístico)

LOAD_DATASET_ON_STARTUP=true uv run uvicorn app.main:app --reload --port 8000
```

Luego visita:
- `http://localhost:8000/api/v1/health` — liveness check
- `http://localhost:8000/docs` — Swagger UI
- `http://localhost:8000/openapi.json` — schema OpenAPI (consumido por el codegen del frontend)
- `http://localhost:8000/api/v1/status/ai` — flags de presencia de modelos ML

## Capas de IA

- **Motor de reglas** — 21 reglas (14 FS aditivas + 7 RF duras) → `score` 0-100 + semáforo 🟢🟡🔴.
- **ML supervisado** — LightGBM + SHAP (top-3 factores) como opinión complementaria.
- **Anomalía** — IsolationForest + vecino "normal" más cercano.
- **Similitud narrativa (NLP)** — embeddings (OpenAI `text-embedding-3-small` por defecto) + pgvector.
- **Agente LangGraph** — responde las 12 preguntas obligatorias en lenguaje natural (SSE).
- **Panel multiagente** — 4 especialistas LLM debaten el caso + moderador (`POST /claims/{id}/panel`, SSE).

Detalle completo en [`docs/uso_ia.md`](./docs/uso_ia.md) y [`docs/arquitectura.md`](./docs/arquitectura.md).

## Quality gates

```bash
uv run ruff check                # lint
uv run ruff format               # format
uv run mypy app                  # typecheck
uv run pytest -q                 # tests
```

## Migraciones de base de datos

```bash
uv run alembic revision --autogenerate -m "mensaje"
uv run alembic upgrade head
uv run alembic downgrade -1
```

## Entrenamiento de modelos

```bash
uv run python -m notebooks._training.train_all     # genera data/models/*.txt y *.joblib
```

## Estructura

Ver [`CLAUDE.md §3`](./CLAUDE.md) para la arquitectura y convenciones completas. El esqueleto principal:

- `app/api/` — routers FastAPI (delgados): `auth`, `claims`, `agent`, `panel`, `imports`, `documents`, `reviews`, `insights`, `audit`, `conversations`, `asegurados`, `network`, `rules`, `reports`, `status`, `health`
- `app/core/` — config, logging, errores, lifespan
- `app/domain/` — lógica de dominio pura (sin I/O): `rules/`, `ml/`, `anomaly/`, `similarity/`, `claims/`, `auth/`
- `app/use_cases/` — orquestadores: `score_claim`, `ask_agent`, `analyze_panel/`, `import_claims/`, `reviews/`, `conversations/`, `generate_dataset/`, `load_dataset/`, `transcribe_audio`, `upload_claim_document*`
- `app/agents/` — grafos LangGraph: `claims_agent/` + `fraud_panel/`
- `app/infrastructure/` — ports + adapters: `llm/`, `embeddings/`, `vectorstore/`, `ml/`, `anomaly/`, `auth/`, `storage/`, `speech/` (Whisper), `ocr/`, `audit/`, `rule_changes/`, `db/`
- `app/repositories/` — acceso a datos con `AsyncSession`
- `app/schemas/` — DTOs pydantic (superficie OpenAPI)
- `tests/` — suite pytest · `alembic/` — migraciones · `docker/` — Dockerfile · `notebooks/` — EDA + entrenamiento
