# CLAUDE.md — Backend (FastAPI + LangGraph)

This file governs everything inside `hackiaton_agent_ai_3.0_backend/`. Read the [root `CLAUDE.md`](../CLAUDE.md) first for cross-stack rules.

> If you're an AI assistant and you're about to run `pip install`, edit `requirements.txt`, drop a 400-line `agent.py`, or `import openai` in feature code — **stop**. We use `uv`, ports/adapters, and small files. See §1 and §2.

---

## 1. Stack

- **Python 3.12+**
- **FastAPI** — HTTP layer.
- **LangGraph** — primary orchestration framework for all agents.
- **LangChain** — only where it earns its keep (document loaders, splitters, embeddings wrappers, retrievers). **Not** used for chains — LangGraph owns orchestration.
- **PostgreSQL via Supabase** — database + auth + storage.
- **pgvector** — vector search (see §8 for the decision).
- **Pydantic v2** + `pydantic-settings` — DTOs, validation, config.
- **asyncpg** (or SQLAlchemy 2.x async) — database access. Pick one in the first PR and stick to it.
- **httpx** — HTTP client.
- **uvicorn** — ASGI server.
- **pytest** + **pytest-asyncio** — tests.
- **ruff** + **mypy** (or pyright) — lint + typecheck.

### Package manager: **`uv` (mandatory)**

- **No `pip`. No `poetry`. No `pipenv`. No hand-edited `requirements.txt`.**
- Source of truth: `pyproject.toml` + `uv.lock`. Both committed.
- Common commands:
  ```bash
  uv sync                          # install deps from lockfile
  uv sync --frozen                 # CI mode: fail if lockfile is stale
  uv add <pkg>                     # add dep (writes pyproject + lock)
  uv add --dev <pkg>               # add dev dep
  uv remove <pkg>                  # remove dep
  uv run <cmd>                     # run a command inside the project env
  uv run uvicorn app.main:app --reload
  uv run pytest
  uv run ruff check
  uv run mypy app
  ```
- Dockerfile uses `uv sync --frozen --no-dev` in the build stage. No `pip install` anywhere in CI or images.

---

## 2. Hard rules for Claude Code

- **One responsibility per file.** Aim for < 200 LOC per module. If you're about to write a 400-line `chat_agent.py`, split nodes into separate files first.
- **Types everywhere.** `pydantic.BaseModel` for every public input/output. `TypedDict` for graph state. No untyped `dict`. No `Any` in public signatures.
- **No business logic in routes.** Routes parse input, call a use case, return the response.
- **No business logic in graph nodes.** Nodes call use cases or domain services. They don't reach into the database.
- **No direct provider SDK calls in feature code.** `import openai` (or `anthropic`) only inside `infrastructure/llm/`. Everywhere else, use the `LLMProvider` port.
- **No hardcoded model names.** Read from `settings.LLM_DEFAULT_MODEL` (or task-specific settings).
- **Prompts live in files.** `app/prompts/{name}.v{n}.md`. Loaded by id via `PromptLoader`. **Never** inline a multi-line prompt in a node.
- **Structured outputs always.** Every tool input and every LLM "give me X" call has a pydantic schema. Reject free-form text where you need data.
- **Use `async` end-to-end.** No blocking I/O on the event loop. If you must call sync code, use `asyncio.to_thread`.

---

## 3. Clean architecture / folder structure

```
app/
├── api/                           ← FastAPI routers — THIN
│   ├── v1/
│   │   ├── chat.py                ← POST /chat, POST /chat/stream
│   │   ├── files.py               ← POST /files, GET /files/{id}/events (SSE)
│   │   ├── auth.py                ← POST /auth/session, POST /auth/session/refresh
│   │   └── health.py
│   └── deps.py                    ← FastAPI dependencies (current_user, db, providers)
├── core/
│   ├── config.py                  ← Settings(BaseSettings) — pydantic-settings
│   ├── logging.py                 ← structured (JSON) logging with request_id
│   └── errors.py                  ← AppError hierarchy + FastAPI exception handlers
├── domain/                        ← PURE — no I/O, no frameworks
│   ├── chat/                      ← entities: Message, Thread; value objects; domain errors
│   ├── memory/
│   └── files/
├── use_cases/                     ← orchestrators — call repos + agents + ports
│   ├── chat/
│   │   ├── send_message.py
│   │   └── stream_message.py
│   ├── rag/
│   │   ├── ingest.py
│   │   └── retrieve.py
│   ├── memory/
│   └── uploads/
├── agents/                        ← LangGraph graphs + nodes — ONE GRAPH PER USE CASE
│   ├── chat_agent/
│   │   ├── graph.py               ← build_graph()
│   │   ├── state.py               ← ChatState(TypedDict)
│   │   ├── nodes/                 ← ONE FILE PER NODE
│   │   │   ├── route.py
│   │   │   ├── retrieve.py
│   │   │   ├── generate.py
│   │   │   └── summarize_memory.py
│   │   └── edges.py
│   ├── router_agent/
│   └── tools/                     ← ONE FILE PER TOOL
│       ├── web_search.py
│       └── doc_lookup.py
├── infrastructure/                ← adapters behind ports
│   ├── llm/
│   │   ├── ports.py               ← LLMProvider Protocol
│   │   ├── openai_adapter.py
│   │   ├── anthropic_adapter.py
│   │   └── local_adapter.py       ← (optional) Ollama
│   ├── embeddings/
│   │   ├── ports.py               ← EmbeddingsProvider Protocol
│   │   └── openai_adapter.py
│   ├── vectorstore/
│   │   ├── ports.py               ← VectorStore Protocol
│   │   └── pgvector_adapter.py
│   ├── db/                        ← asyncpg pool / SQLAlchemy session factory
│   ├── storage/                   ← Supabase Storage adapter
│   └── auth/
│       └── supabase_jwt.py        ← JWKS verifier
├── repositories/                  ← concrete repos behind domain ports
│   ├── chat_repo.py
│   ├── memory_repo.py
│   └── file_repo.py
├── schemas/                       ← API DTOs — what the wire sees (pydantic)
│   ├── chat.py                    ← ChatStreamEvent discriminated union lives here
│   ├── files.py
│   └── auth.py
├── prompts/
│   ├── chat_system.v1.md
│   └── router.v1.md
└── main.py                        ← FastAPI app factory: app = create_app()
tests/
docker/
  └── Dockerfile
docker-compose.yml
supabase/
  └── migrations/
```

**Dependency direction (the only one that's allowed):**

```
api ───▶ use_cases ───▶ domain
              │
              ├──▶ repositories ──▶ infrastructure/db
              ├──▶ agents ─────────▶ infrastructure/llm + tools
              └──▶ infrastructure/* (ports only — adapters wired in deps.py)
```

`domain/` imports nothing from anywhere else. `agents/` calls use cases or ports, not repositories directly. `api/` never imports from `infrastructure/` directly — go through `deps.py`.

---

## 4. Ports & adapters

Every external dependency is a `Protocol`. Use cases and graphs depend on the port; concrete adapters are wired in `api/deps.py`.

```python
# infrastructure/llm/ports.py
from typing import Protocol, AsyncIterator
from .types import LLMResult, LLMEvent, Message, ToolSpec, ResponseFormat

class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
    ) -> LLMResult: ...

    def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[LLMEvent]: ...
```

```python
# api/deps.py
def get_llm() -> LLMProvider:
    match settings.LLM_PROVIDER:
        case "openai":    return OpenAIAdapter(settings)
        case "anthropic": return AnthropicAdapter(settings)
        case "local":     return LocalAdapter(settings)
        case _: raise ConfigError(f"unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")
```

Same shape for `EmbeddingsProvider`, `VectorStore`, `Storage`, `AuthVerifier`.

---

## 5. LangGraph conventions

- **One graph per use case.** `chat_agent`, `rag_agent`, `router_agent`. Never a single mega-graph.
- **State is a `TypedDict`** with explicit reducers (`Annotated[..., add_messages]` for message lists, etc.). Never a free-form dict.
- **Nodes are pure-ish functions** `async def node(state: ChatState) -> dict`. They return a partial state to merge. **No direct DB / network access** — they call use cases or ports passed in via the graph's compile-time config.
- **Tools have schemas.** Every tool defines a pydantic input schema and a pydantic output schema. Use LangChain's `@tool` decorator if convenient, or a thin in-house `Tool` interface.
- **Streaming events.** Use `graph.astream_events(version="v2", ...)`. Translate the LangGraph event stream into our wire-shape `ChatStreamEvent` (see §7) in `use_cases/chat/stream_message.py`. Frontend should never see raw LangGraph events.
- **Prompts loaded by id.** `prompt = PromptLoader.load("chat_system", "v1")`. Never inline > 5 lines of prompt in a node.
- **Prompt versioning.** Bump the version (`chat_system.v2.md`) when you change semantics; keep the old one around until callers migrate. Never overwrite a `vN` file with breaking changes.
- **Reactive agents** (where used) live in their own graphs with their own state; never bolt them onto the chat graph.

Example node:

```python
# agents/chat_agent/nodes/generate.py
async def generate(state: ChatState, *, llm: LLMProvider, prompts: PromptLoader) -> dict:
    system = prompts.load("chat_system", "v1")
    messages = [Message(role="system", content=system), *state["messages"]]
    result = await llm.complete(messages, model=state["model"], response_format=AssistantReply)
    return {"messages": [result.message]}
```

---

## 6. Provider abstraction

- **`LLMProvider`** — `complete()` + `stream()` (§4).
- **`EmbeddingsProvider`** — `embed(texts: list[str]) -> list[list[float]]`.
- **`VectorStore`** — `upsert()`, `query()`, `delete()` keyed by `owner_id` + `source_id`.
- **`Storage`** — `put()`, `signed_url()`, `delete()`.
- **`AuthVerifier`** — `verify(jwt: str) -> User`.

Selection by env: `LLM_PROVIDER`, `EMBEDDINGS_PROVIDER`, `VECTOR_STORE`, etc. Default to OpenAI for LLM + embeddings during the hackathon.

---

## 7. Real-time / streaming

**SSE is the default** for AI streaming.

- HTTP is enough — token streams are unidirectional from server → client.
- FastAPI `StreamingResponse(media_type="text/event-stream")` plays nicely with proxies, CDNs, and browser devtools.
- Reserve WebSockets for genuinely bidirectional features (multi-user presence, collaborative editing). We don't need them today.

**Endpoint:**

```
POST /api/v1/chat/stream
  body: { thread_id?: str, prompt: str, ... }
  returns: text/event-stream
  events: ChatStreamEvent (one per SSE message, payload as JSON)
```

**`ChatStreamEvent`** (in `schemas/chat.py`, surfaces to OpenAPI, used by the frontend — must match `hackiaton_agent_ai_3.0_frontend/CLAUDE.md` §7):

```python
class TokenEvent(BaseModel):
    type: Literal["token"]
    data: TokenData  # { delta: str, message_id: str }

class ToolCallEvent(BaseModel):
    type: Literal["tool_call"]
    data: ToolCallData  # { tool: str, args: Any, call_id: str }

class ToolResultEvent(BaseModel):
    type: Literal["tool_result"]
    data: ToolResultData  # { call_id: str, result: Any }

class AgentStepEvent(BaseModel):
    type: Literal["agent_step"]
    data: AgentStepData  # { node: str, meta: Any | None }

class ErrorEvent(BaseModel):
    type: Literal["error"]
    data: ErrorData  # { code: str, message: str }

class DoneEvent(BaseModel):
    type: Literal["done"]
    data: DoneData  # { message_id: str }

ChatStreamEvent = Annotated[
    TokenEvent | ToolCallEvent | ToolResultEvent | AgentStepEvent | ErrorEvent | DoneEvent,
    Field(discriminator="type"),
]
```

Always emit a final `done` (or `error`) event. Always flush after each event.

---

## 8. Vector DB decision — **pgvector** (chosen)

**Decision: use `pgvector`. Reject Chroma for this project.**

**Reasoning:**

- Supabase Postgres is already the system of record. Embeddings inside the same database means **no second datastore** to deploy, monitor, back up, or sync.
- Vector queries can `JOIN` against relational tables in a single SQL statement — essential for RAG with ownership/auth filters (`WHERE owner_id = $1`).
- Supabase has first-class pgvector support: migrations, RLS, HNSW and IVFFlat indexes built in.
- Chroma is excellent as a local-first standalone store, but adds operational surface area (separate container, separate persistence layer, separate auth story, separate backup strategy) for a capability we already have.
- At hackathon scale (< 10M vectors), pgvector + HNSW is fast (single-digit-ms p95 for typical RAG workloads).

**When to revisit:** if vector count grows past ~10M with sub-50ms p95 latency requirements that HNSW tuning can't meet, swap the `VectorStore` adapter to Qdrant or Weaviate. The port makes this a localized change.

**Schema convention:**

```sql
create extension if not exists vector;

create table embeddings (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid not null references auth.users(id) on delete cascade,
  source_type   text not null,                           -- 'file' | 'memory' | ...
  source_id     uuid not null,
  chunk_index   int  not null,
  content       text not null,
  embedding     vector(1536) not null,                    -- dimension matches embedding model
  metadata      jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);

create index on embeddings using hnsw (embedding vector_cosine_ops);
create index on embeddings (owner_id, source_type);
```

**Query rule:** every vector query filters by `owner_id` (enforced via Supabase RLS as a defense-in-depth).

---

## 9. RAG pipeline

- **`use_cases/rag/ingest.py`** — `load → split → embed → upsert`. Loaders/splitters from LangChain are fine. The orchestration is ours.
- **`use_cases/rag/retrieve.py`** — `embed(query) → vector_store.query(owner_id, top_k) → optional rerank → return chunks`.
- Both run async. Ingest is fired from `POST /files` via a background task.

---

## 10. Memory

- **Short-term** (per-thread): message history persisted via `chat_repo`. The chat graph reads it on entry, writes it on exit.
- **Long-term** (cross-thread): a `summarize_memory` graph node periodically summarizes a thread and stores the summary as an embedding in `embeddings` with `source_type='memory'`. Retrieval at the start of a new thread surfaces relevant prior context.
- **Memory writes happen in a dedicated node**, never inline in unrelated nodes.

---

## 11. Authentication

- **Supabase JWT.** Verified server-side against Supabase's JWKS by `infrastructure/auth/supabase_jwt.py` (cache the JWKS, refresh on `kid` miss).
- **`api/deps.py`** exposes:
  ```python
  async def get_current_user(token: str = Depends(bearer_scheme)) -> User: ...
  ```
- Every protected route depends on `get_current_user`. Public routes opt out explicitly.
- **Refresh flow:** `POST /api/v1/auth/session` takes a Supabase access+refresh pair, sets the refresh token as an `HttpOnly; Secure; SameSite=Lax` cookie, returns the access token in the body. `POST /api/v1/auth/session/refresh` reads the cookie, exchanges via Supabase, returns a new access token. Frontend access token never touches `localStorage`.
- **Never roll custom auth.** Never log JWTs. Never return the service-role key. The Supabase service-role key is server-only.

---

## 12. File uploads

- **`POST /api/v1/files`** (multipart): `infrastructure/storage/` saves to Supabase Storage, `file_repo` records the file row, route returns `{ file_id }`.
- **Validation:** mime allow-list + size limit (configurable in `settings`). Reject early; return a typed error.
- **Virus-scan port** (`Scanner` Protocol) — no-op adapter for hackathon, real adapter post-hackathon. Wire site: ingest pipeline before embedding.
- **Async ingestion:** route enqueues a `BackgroundTask` running the `rag/ingest.py` use case. For the hackathon, `fastapi.BackgroundTasks` is fine. Post-hackathon, swap to a queue (Redis/RQ, Cloud Tasks) — the use case stays unchanged.
- **`GET /api/v1/files/{file_id}/events`** (SSE): emits `FileIngestEvent` (`uploaded`, `parsing`, `embedding`, `ready`, `error`) so the frontend can show progress. Shape matches frontend §10.

---

## 13. Database & migrations

- Migrations live in `supabase/migrations/` and are applied via the Supabase CLI.
- Repositories use **`asyncpg`** (or SQLAlchemy 2.x async — pick one in the first DB PR). Choice committed to one of them.
- **No raw SQL outside `repositories/`.** No SQLAlchemy queries in routes, use cases, or nodes.
- Connection pool created once at app startup (`main.py` lifespan), passed via `Depends`.

---

## 14. Configuration

```python
# core/config.py
class Settings(BaseSettings):
    # app
    APP_ENV: Literal["dev","test","prod"] = "dev"
    LOG_LEVEL: str = "INFO"

    # supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: SecretStr
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # llm
    LLM_PROVIDER: Literal["openai","anthropic","local"] = "openai"
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None

    # embeddings
    EMBEDDINGS_PROVIDER: Literal["openai"] = "openai"
    EMBEDDINGS_MODEL: str = "text-embedding-3-small"
    EMBEDDINGS_DIM: int = 1536

    # uploads
    UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024
    UPLOAD_ALLOWED_MIME: list[str] = ["application/pdf","text/plain","text/markdown"]

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

settings = Settings()  # cached
```

- All env vars listed (with descriptions) in `.env.example`.
- **No `os.getenv` anywhere else.** Code reads from `settings`.

---

## 15. Errors & logging

- `core/errors.py` defines:
  ```python
  class AppError(Exception): code: str; status_code: int = 500; message: str
  class NotFound(AppError): status_code = 404
  class Unauthorized(AppError): status_code = 401
  class ValidationFailed(AppError): status_code = 422
  class ProviderError(AppError): status_code = 502
  # ...
  ```
- `main.py` registers exception handlers mapping `AppError` → `JSONResponse({code, message})`.
- **Structured logging (JSON)** with `request_id` correlation injected by middleware.
- **Never `print()`.** Use the project logger.
- **Never log secrets** (JWTs, API keys, file contents).

---

## 16. Testing

- `pytest` + `pytest-asyncio`. Run with `uv run pytest`.
- **Unit tests** for use cases — mock the ports.
- **Integration tests** for repositories against a test Postgres (docker-compose service `postgres-test`).
- **One smoke test per route** that hits the app via `httpx.AsyncClient(app=app)`.
- **Don't chase coverage** during the hackathon. Cover the critical path: auth, chat stream, file ingest, RAG retrieval.

---

## 17. Docker & CI

- `docker/Dockerfile` — multi-stage:
  ```dockerfile
  FROM python:3.12-slim AS builder
  COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
  WORKDIR /app
  COPY pyproject.toml uv.lock ./
  RUN uv sync --frozen --no-dev --no-install-project
  COPY . .
  RUN uv sync --frozen --no-dev

  FROM python:3.12-slim AS runtime
  COPY --from=builder /app /app
  WORKDIR /app
  ENV PATH="/app/.venv/bin:$PATH"
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
- `docker-compose.yml` — app + `postgres` (with pgvector image) for local dev.
- **GitHub Actions** on PR:
  1. `astral-sh/setup-uv@v3`
  2. `uv sync --frozen`
  3. `uv run ruff check`
  4. `uv run mypy app` (or `pyright`)
  5. `uv run pytest -q`

---

## 18. Anti-patterns (do NOT do these)

- ❌ Business logic in routes → move to a use case.
- ❌ Business logic in graph nodes → move to a use case or domain service.
- ❌ Giant agent files → split into per-node files under `agents/<name>/nodes/`.
- ❌ Inline prompts > 5 lines → move to `app/prompts/{name}.v1.md`.
- ❌ `import openai` / `import anthropic` outside `infrastructure/llm/` → use the `LLMProvider` port.
- ❌ Hardcoded model names → read from `settings`.
- ❌ Untyped LLM outputs → use structured outputs + pydantic parsing.
- ❌ Free-form `dict` graph state → use a `TypedDict`.
- ❌ `Any` in public signatures → narrow it.
- ❌ Mutable module-level state → put it on the app via lifespan.
- ❌ Catching bare `Exception` → catch what you can handle; let the global handler do the rest.
- ❌ `os.getenv("X")` outside `core/config.py` → use `settings`.
- ❌ Raw SQL outside `repositories/` → use the repo.
- ❌ Logging secrets / JWTs / file contents → never.
- ❌ Using `pip`, `poetry`, `pipenv`, or editing `requirements.txt` → **`uv` only**.
- ❌ Blocking I/O in async paths → `await` it, or push it to `asyncio.to_thread`.

---

## 19. AI-assistant checklist (Claude Code, Cursor, Copilot)

Before you submit a change, verify:

- [ ] All deps added via `uv add`; `pyproject.toml` and `uv.lock` are both committed.
- [ ] No file > 250 LOC. Agent files split into nodes.
- [ ] Routes are thin; logic lives in use cases.
- [ ] Graph nodes touch ports/use cases only, not repositories or external SDKs directly.
- [ ] Provider SDKs only imported inside `infrastructure/llm/` (or analogous adapters).
- [ ] All LLM "give me X" calls use structured outputs with a pydantic schema.
- [ ] Prompts in `app/prompts/`, loaded by id.
- [ ] `ChatStreamEvent` shape matches the frontend's definition. If you changed it, regen frontend types.
- [ ] Every protected route depends on `get_current_user`.
- [ ] No JWT or secret in logs.
- [ ] Vector queries filter by `owner_id`.
- [ ] `uv run ruff check && uv run mypy app && uv run pytest -q` all green.
