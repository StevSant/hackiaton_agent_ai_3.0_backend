# hackiaton_agent_ai_3.0_backend

FastAPI + LangGraph backend for the Hackiaton 3.0 Agent AI project. See [`CLAUDE.md`](./CLAUDE.md) for conventions.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (package manager — mandatory, never use `pip`)
- Docker + Docker Compose (for the local Postgres + pgvector instance)

## Setup

```bash
uv sync                          # install deps from lockfile
cp .env.example .env             # fill in real values
```

## Run

```bash
docker compose up -d db          # start Postgres+pgvector locally
uv run uvicorn app.main:app --reload --port 8000
```

Then visit:
- `http://localhost:8000/api/v1/health` — liveness check
- `http://localhost:8000/docs` — Swagger UI
- `http://localhost:8000/openapi.json` — OpenAPI schema (consumed by frontend codegen)

## Quality gates

```bash
uv run ruff check                # lint
uv run ruff format               # format
uv run mypy app                  # typecheck
uv run pytest -q                 # tests
```

## Database migrations

```bash
uv run alembic revision --autogenerate -m "add chat tables"
uv run alembic upgrade head
uv run alembic downgrade -1
```

## Layout

See [`CLAUDE.md §3`](./CLAUDE.md) for the architecture and folder conventions. The skeleton lays out:

- `app/api/` — FastAPI routers (thin)
- `app/core/` — config, logging, errors
- `app/domain/` — pure domain logic (no I/O)
- `app/use_cases/` — orchestrators
- `app/agents/` — LangGraph graphs + nodes
- `app/infrastructure/` — ports + adapters (LLM, embeddings, vectorstore, storage, auth, db)
- `app/repositories/` — concrete data access
- `app/schemas/` — wire-shape Pydantic DTOs (surfaces to OpenAPI)
- `app/prompts/` — versioned prompt files (`name.vN.md`)
- `tests/` — pytest suite
- `alembic/` — DB migrations
- `docker/` — Dockerfile + .dockerignore
