# CLAUDE.md — Backend (FastAPI + LangGraph)

This file governs everything inside `hackiaton_agent_ai_3.0_backend/`. Read the [root `CLAUDE.md`](../CLAUDE.md) first for cross-stack rules, and especially **§2 Challenge spec — ground truth** (Aseguradora del Sur). The product spec lives at `docs/superpowers/specs/2026-05-26-centinela-claims-design.md`.

> If you're an AI assistant and you're about to run `pip install`, edit `requirements.txt`, drop a 400-line `agent.py`, or `import openai` in feature code — **stop**. We use `uv`, ports/adapters, and small files. See §1 and §2.

---

## 1. Stack

- **Python 3.12+**
- **FastAPI** — HTTP layer.
- **LangGraph** — primary orchestration framework for the claims agent.
- **LangChain** — only where it earns its keep (embeddings wrappers, retrievers). **Not** used for chains — LangGraph owns orchestration.
- **PostgreSQL with `pgvector` extension** — relational store + vector store for narrative similarity. Run locally via `docker-compose`.
- **Pydantic v2** + `pydantic-settings` — DTOs, validation, config.
- **SQLAlchemy 2.0 (async, declarative) + asyncpg driver + Alembic** — ORM, session management, migrations. Repos take `AsyncSession`. Raw asyncpg is only used inside `use_cases/load_dataset.py` for bulk `COPY`. *(Decision locked 2026-05-26 — see design spec §13.)*
- **httpx** — HTTP client.
- **uvicorn** — ASGI server.
- **LightGBM** + **shap** — supervised fraud probability model + per-feature explanation.
- **scikit-learn** — Isolation Forest for anomaly detection + utility transforms.
- **Embeddings** — narrative embeddings via the `EmbeddingsProvider` port. **Default: OpenAI `text-embedding-3-small` (384-dim).** Local alternative: **sentence-transformers** `paraphrase-multilingual-MiniLM-L12-v2` (also 384-dim, no API calls), selectable via `EMBEDDINGS_PROVIDER=sentence_transformers`.
- **pandas** — dataset ingestion + feature engineering inside `use_cases/load_dataset.py`.
- **PyJWT (`pyjwt[crypto]`) + bcrypt** — local JWT issuance + verification + password hashing for V0 auth. **No** Supabase Auth, **no** OAuth.
- **openai** — sole LLM provider for the hackathon (model: `gpt-4o-mini`). **Only** imported under `infrastructure/llm/`. The `LLMProvider` port is preserved so a post-hackathon swap to Anthropic or another provider is one adapter file. **No `anthropic` SDK in pyproject.** *(Decision locked 2026-05-26 — was originally "Anthropic primary".)*
- **pytest** + **pytest-asyncio** — tests. Real-LLM calls are gated behind `@pytest.mark.integration`; unit tests use `InMemoryFakeLLM`.
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

- **One responsibility per file.** Aim for < 200 LOC per module. **Each fraud rule (FS-NN / RF-NN) is its own file** — see §9.
- **Types everywhere.** `pydantic.BaseModel` for every public input/output. `TypedDict` for graph state. No untyped `dict`. No `Any` in public signatures.
- **No business logic in routes.** Routes parse input, call a use case, return the response.
- **No business logic in graph nodes.** Nodes call use cases or domain services. They don't reach into the database.
- **No direct provider SDK calls in feature code.** `import anthropic` / `import openai` only inside `infrastructure/llm/`. Everywhere else, use the `LLMProvider` port.
- **No hardcoded model names, no hardcoded fraud-rule thresholds, no hardcoded URLs.** Read from `settings.*`. Per-rule point bands live in `app/domain/rules/config.py` (or YAML next to it), never inline.
- **Prompts live in files.** `app/agents/claims_agent/prompts/{name}.v{n}.md`. Loaded by id via `PromptLoader`. **Never** inline a multi-line prompt in a node.
- **Structured outputs always.** Every tool input and every LLM "give me X" call has a pydantic schema. Reject free-form text where you need data.
- **Schema fields are Spanish `snake_case`** because the wire contract is Spanish (root CLAUDE.md §2.8). Pydantic models mirror the data-dictionary verbatim.
- **Never call a claim a "fraude" in any string** that may surface to a user (UI, API, logs at INFO+). Use `posible_fraude`, `alerta`, `requiere_revision`. Internal Python identifiers can use `fraud_*` freely.
- **Use `async` end-to-end.** No blocking I/O on the event loop. If you must call sync code (LightGBM `.predict`, sentence-transformer encode), use `asyncio.to_thread`.
- **Model artifacts use native serializers, not generic pickle.** LightGBM → `Booster.save_model("…txt")`. Isolation Forest → `joblib.dump(model, "…joblib")`. Never load model artifacts from untrusted sources — they only come from our own `notebooks/` training runs.

---

## 3. Clean architecture / folder structure

```
app/
├── api/                           ← FastAPI routers — THIN
│   ├── v1/
│   │   ├── auth.py                ← POST /auth/login (JSON, for Angular) + POST /auth/token (form, for Swagger Authorize) (V0)
│   │   ├── claims.py              ← GET /claims, GET /claims/{id}, POST /claims/{id}/rescore,
│   │   │                            POST /claims/{id}/escalate (analista), POST /claims/{id}/resolve (antifraude),
│   │   │                            PATCH /claims/{id} (debug, antifraude)
│   │   ├── agent.py               ← POST /agent/ask (SSE)
│   │   ├── reports.py             ← GET /reports/executive (stretch)
│   │   └── health.py
│   └── deps.py                    ← FastAPI dependencies (db session, providers, get_current_user)
├── core/
│   ├── config.py                  ← Settings(BaseSettings) — pydantic-settings
│   ├── logging.py                 ← structured (JSON) logging with request_id
│   └── errors.py                  ← AppError hierarchy + FastAPI exception handlers
├── domain/                        ← PURE — no I/O, no frameworks
│   ├── auth/                      ← User, Role, AccessToken VO (V0)
│   ├── claims/                    ← Claim, ClaimRiskScore, Tier, RuleActivation, FactorContribution, SimilarClaim,
│   │                                WorkflowStatus, WorkflowTransition (V2.6)
│   ├── rules/
│   │   ├── ports.py               ← FraudRule Protocol
│   │   ├── signals/               ← ONE FILE PER FS-NN (FS_01_..._py)
│   │   ├── hard/                  ← ONE FILE PER RF-NN (RF_01_..._py)
│   │   ├── aggregator.py          ← combines activations → ClaimRiskScore
│   │   ├── tier.py                ← score → 🟢🟡🔴 mapping + hard-rule overrides
│   │   └── config.py              ← per-rule weights / thresholds (loaded from env or YAML)
│   ├── ml/                        ← FraudClassifier port, FactorContribution VO
│   ├── anomaly/                   ← AnomalyDetector port
│   └── similarity/                ← NarrativeSimilarity port, SimilarClaim VO
├── use_cases/                     ← orchestrators — call repos + agents + ports
│   ├── auth/
│   │   └── login.py               ← verify creds, issue JWT (V0)
│   ├── score_claim.py             ← runs rules + ml + anomaly + similarity → ClaimRiskScore
│   ├── escalate_claim.py          ← analista action — flips workflow_status pending → escalated (V2.6)
│   ├── resolve_claim.py           ← antifraude action — flips workflow_status escalated → resolved (V2.6)
│   ├── list_claims.py
│   ├── get_claim_detail.py
│   ├── ask_agent.py               ← drives the LangGraph claims agent
│   ├── generate_report.py         ← stretch
│   └── load_dataset.py            ← CSV → Postgres on app startup (raw asyncpg COPY)
├── agents/                        ← LangGraph graphs + nodes — ONE GRAPH PER USE CASE
│   └── claims_agent/
│       ├── graph.py               ← build_graph()
│       ├── state.py               ← ClaimsAgentState(TypedDict)
│       ├── nodes/                 ← ONE FILE PER NODE
│       │   ├── route.py           ← intent classifier
│       │   ├── query_claims.py    ← Q1, Q9, Q12 (ranked lists)
│       │   ├── explain_case.py    ← Q2 (per-claim breakdown)
│       │   ├── aggregate.py       ← Q3, Q4, Q5, Q6, Q8, Q10 (group-bys)
│       │   ├── documents.py       ← Q7 (missing docs)
│       │   ├── summarize.py       ← Q11 (executive summary)
│       │   └── compose.py         ← final Spanish renderer with citations
│       ├── tools/                 ← ONE FILE PER TOOL, pydantic input + output
│       │   ├── query_claims_tool.py
│       │   ├── get_claim_detail_tool.py
│       │   ├── aggregate_by_dimension_tool.py
│       │   ├── missing_documents_tool.py
│       │   └── summarize_critical_tool.py
│       └── prompts/
│           ├── claims_system.v1.md
│           └── compose.v1.md
├── infrastructure/                ← adapters behind ports
│   ├── auth/                      ← jwt_issuer.py, password_hasher.py, env_seeded_user_repo.py (V0; reads AUTH_SEED_USERS env JSON, hashes at boot)
│   ├── llm/
│   │   ├── ports.py               ← LLMProvider Protocol
│   │   ├── openai_adapter.py      ← sole provider for the hackathon
│   │   └── fake_llm.py            ← InMemoryFakeLLM for unit tests (canned fixture-driven)
│   ├── embeddings/
│   │   ├── ports.py               ← EmbeddingsProvider Protocol
│   │   └── sentence_transformers_adapter.py
│   ├── vectorstore/
│   │   ├── ports.py               ← NarrativeSimilarity Protocol (uses VectorStore underneath)
│   │   ├── pgvector_adapter.py    ← primary
│   │   └── in_memory_adapter.py   ← 2-hr fallback if pgvector blocks
│   ├── ml/
│   │   └── lightgbm_adapter.py    ← loads data/models/fraud_lgbm.txt + computes SHAP
│   ├── anomaly/
│   │   └── isolation_forest_adapter.py
│   └── db/                        ← SQLAlchemy 2.0 async engine + session factory + ONE MODEL PER FILE under models/
├── repositories/                  ← AsyncSession-backed repos
│   ├── claims_repo.py
│   ├── polizas_repo.py
│   ├── asegurados_repo.py
│   ├── proveedores_repo.py
│   └── documentos_repo.py
├── schemas/                       ← API DTOs — what the wire sees (pydantic)
│   ├── auth.py                    ← LoginRequest, LoginResponse, CurrentUser (V0)
│   ├── claim.py                   ← Claim, ClaimSummary, ClaimDetail, ClaimPatch (debug)
│   ├── risk.py                    ← ClaimRiskScore, RuleActivation, FactorContribution, SimilarClaim
│   ├── agent.py                   ← AgentAskRequest, ChatStreamEvent (reused for the agent SSE)
│   └── reports.py                 ← ExecutiveReport (stretch)
└── main.py                        ← FastAPI app factory: app = create_app()
alembic/
├── env.py                         ← target_metadata = Base.metadata
└── versions/                      ← autogenerated migrations
data/
├── raw/                           ← Kaggle source (gitignored if > 50 MB)
├── processed/                     ← schema-adapted CSVs (committed)
├── synthetic/                     ← generator output (committed)
└── models/                        ← fraud_lgbm.txt, anomaly_iforest.joblib (committed if < 50 MB)
                                   ← (No data/seeds/. Seeded users live in the AUTH_SEED_USERS env var only — see V0.)
notebooks/
├── 01_exploracion_datos.ipynb
├── 02_modelo_fraude.ipynb
└── 03_evaluacion_modelo.ipynb
docs/
├── arquitectura.md                ← diagram + flow
├── modelo_datos.md                ← tables + relations
├── reglas_negocio.md              ← FS/RF catalog with point bands
├── uso_ia.md                      ← ML + agent explanation, metrics
└── limitaciones.md                ← risks, false positives, bias notes
tests/
├── (unit + integration)
└── integration/                   ← real-LLM smoke tests, gated by @pytest.mark.integration
docker/
  └── Dockerfile
docker-compose.yml                 ← app + postgres+pgvector
```

**Deferred (out of scope for the hackathon submission — do NOT scaffold):** `use_cases/rag/`, `domain/memory/`, `agents/router_agent/`. See the spec §11 for the re-introduction trigger.

> **Auth is in scope now (V0):** `infrastructure/auth/`, `domain/auth/`, `use_cases/auth/`, and `api/v1/auth.py` are first-class. They were originally on the deferred list; spec §17 (2026-05-26) added them back as **local JWT only** (no Supabase, no OAuth) for demo-day insurance.

> **The following were originally deferred but landed during the hackathon and are now in scope:**
> - `infrastructure/storage/` — backend file storage adapter for uploaded claim documents.
> - `infrastructure/speech/` — Whisper transcription adapter for the voice-input chat.
> - `use_cases/import_claims/` + `use_cases/upload_claim_document.py` + `upload_claim_documents_bulk.py` + `sync_claim_document.py` + `delete_claim_document.py` — analyst-facing CSV/JSON import + per-claim PDF upload flow.
> - `use_cases/conversations/` + `use_cases/transcribe_audio.py` — conversation history for the agent chat and voice-to-text transcription.
> - `infrastructure/audit/` + `infrastructure/rule_changes/` — append-only in-memory stores feeding the Audit page and the Rules-changes log respectively (added 2026-05-27).
> Treat these as first-class; do not delete them or move them back behind the deferred line.

**Dependency direction (the only one that's allowed):**

```
api ───▶ use_cases ───▶ domain
              │
              ├──▶ repositories ──▶ infrastructure/db
              ├──▶ agents ─────────▶ infrastructure/llm + tools
              └──▶ infrastructure/{ml,anomaly,vectorstore,embeddings} (ports only — adapters wired in deps.py)
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
        case "anthropic": return AnthropicAdapter(settings)
        case "openai":    return OpenAIAdapter(settings)
        case _: raise ConfigError(f"unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")
```

Same shape for `EmbeddingsProvider`, `NarrativeSimilarity` (uses a `VectorStore` underneath), `FraudClassifier`, `AnomalyDetector`.

---

## 5. LangGraph conventions

- **One graph per use case.** Today: `claims_agent` (the 12 NL questions) and `fraud_panel` (the 4-specialist analysis panel, `app/agents/fraud_panel/`). Never a single mega-graph.
- **State is a `TypedDict`** with explicit reducers (`Annotated[..., add_messages]` for message lists). Never a free-form dict.
- **Nodes are pure-ish functions** `async def node(state: ClaimsAgentState) -> dict`. They return a partial state to merge. **No direct DB / network access** — they call use cases or ports passed in via the graph's compile-time config.
- **Tools have schemas.** Every tool defines a pydantic input schema and a pydantic output schema. Use LangChain's `@tool` decorator if convenient, or a thin in-house `Tool` interface.
- **Streaming events.** Use `graph.astream_events(version="v2", ...)`. Translate the LangGraph event stream into our wire-shape `ChatStreamEvent` (see §7) in `use_cases/ask_agent.py`. Frontend should never see raw LangGraph events.
- **Prompts loaded by id.** `prompt = PromptLoader.load("claims_system", "v1")`. Never inline > 5 lines of prompt in a node.
- **Prompt versioning.** Bump the version (`claims_system.v2.md`) when you change semantics; keep the old one around until callers migrate. Never overwrite a `vN` file with breaking changes.

Example node:

```python
# agents/claims_agent/nodes/explain_case.py
async def explain_case(
    state: ClaimsAgentState,
    *,
    get_claim_detail: GetClaimDetail,
    prompts: PromptLoader,
) -> dict:
    detail = await get_claim_detail.run(state["context"]["focus_claim_id"])
    state_msg = ToolResult(call_id="...", result=detail.model_dump())
    return {"tool_results": [detail], "messages": [state_msg]}
```

---

## 6. Provider abstraction

- **`LLMProvider`** — `complete()` + `stream()` (§4). **Default: `openai` (gpt-4o-mini).** No Anthropic SDK in the hackathon build. For tests: `InMemoryFakeLLM` (canned fixture-driven). The port is preserved so post-hackathon swap is one file. *(Decision locked 2026-05-26.)*
- **`EmbeddingsProvider`** — `embed(texts: list[str]) -> list[list[float]]`. Default: OpenAI `text-embedding-3-small` (384-dim). Local alternative: sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`).
- **`NarrativeSimilarity`** — `nearest(claim_id) -> list[SimilarClaim]`. Default: `PgVectorNarrativeSimilarity`. Fallback: `InMemoryNarrativeSimilarity` (numpy cosine).
- **`FraudClassifier`** — `predict(features) -> (probability, factors)`. Default: `LightGBMClassifier` (loads a Booster artifact).
- **`AnomalyDetector`** — `score(features) -> AnomalyScore`. Default: `IsolationForestDetector`.
- **`AuthVerifier`** *(V0)* — `verify(token) -> User`. Default: `JwtIssuer` (HS256, PyJWT, secret from `settings.JWT_SECRET`). Preserved for post-hackathon swap to Supabase JWKS.

Selection by env: `LLM_PROVIDER`, `EMBEDDINGS_PROVIDER`, `VECTOR_STORE`, `FRAUD_CLASSIFIER`, `ANOMALY_DETECTOR`, `AUTH_ENABLED`.

---

## 6b. Auth + RBAC pattern

*(Added 2026-05-26 — see design spec §13 / §17.)*

**Two-role model.** Every authenticated request carries a role in its JWT claim. Two roles exist:
- **`analista`** — primary triage user. Sees all claims, can escalate yellow/red claims to the antifraude unit.
- **`antifraude`** — escalation team. Sees the escalated queue, resolves cases, can run debug operations like `PATCH /claims/{id}`.

**`get_current_user`** decodes the JWT and returns the `User` domain object (with `role`). Applied **router-wide** to every router from V1 onward; only `/health` and `/auth/login` skip it.

**`require_role(role: Role)`** is a **dependency factory**, not a Protocol or a middleware. It returns a callable that depends on `get_current_user` and raises **403** (not 401) when the role mismatches — that's the correct semantic for "authenticated but not authorized":

```python
# app/api/deps.py
from typing import Annotated, Callable
from fastapi import Depends, HTTPException, status
from app.domain.auth.user import User, Role

def require_role(role: Role) -> Callable[[User], User]:
    def _checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "role_required", "message": f"Requires role: {role}"},
            )
        return user
    return _checker
```

**Where to apply it:**
- Apply role gates **only on state-changing endpoints**. Reads (`GET /claims`, `GET /claims/{id}`, `POST /agent/ask`) are open to any authenticated user — both roles need to see the data.
- The matrix lives in design spec §6. Don't fork it; if you add a new gated endpoint, update the spec table in the same PR.
- Apply via FastAPI's `dependencies=[Depends(require_role("antifraude"))]` on the **route decorator**, not buried in the handler body. That makes the gate visible at the routing layer where it should be audited.

**Anti-patterns** (caught in review):
- ❌ Checking `user.role` inside a use case. Use cases are role-agnostic; the gate is enforced at the API layer. If two roles need different behavior from the same use case, write two use cases.
- ❌ Returning 401 instead of 403 for role mismatch — they mean different things to clients.
- ❌ Silently returning empty data when the role is wrong. Always raise. Hide UI controls on the frontend; the backend always tells the truth via 403.
- ❌ Adding new roles ad-hoc. Two roles is the cap for the hackathon; new roles require updating the spec §6 / §13 / §10 first.

---

## 7. Real-time / streaming

**SSE is the default** for the agent's NL responses.

- HTTP is enough — token streams are unidirectional from server → client.
- FastAPI `StreamingResponse(media_type="text/event-stream")` plays nicely with proxies, CDNs, and browser devtools.

**Endpoint:**

```
POST /api/v1/agent/ask
  body: { query: str, context?: { focus_claim_id?: str } }
  returns: text/event-stream
  events: ChatStreamEvent (one per SSE message, payload as JSON)
```

**`ChatStreamEvent`** (in `schemas/agent.py`, surfaces to OpenAPI, used by the frontend — must match `hackiaton_agent_ai_3.0_frontend/CLAUDE.md` §7):

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

Always emit a final `done` (or `error`) event. Always flush after each event. The claims agent emits `agent_step` events for routing decisions (`{node: "route", meta: {intent: "aggregate"}}`) and `tool_call` / `tool_result` for each tool invocation — these power the UI's transparency cards.

---

## 8. Vector DB decision — **pgvector** (chosen)

**Decision: use `pgvector`. Reject standalone vector stores for this project.**

**Reasoning:**

- Postgres is already the system of record (claims, polizas, etc.). Embeddings inside the same database means **no second datastore** to deploy, monitor, back up, or sync.
- Vector queries can `JOIN` against relational tables in a single SQL statement — essential when we need "find the 3 most similar claims to claim X **excluding claims older than 18 months**".
- pgvector has first-class HNSW + IVFFlat indexes; both are fast at hackathon scale (< 10M vectors).

**Hackathon-specific use case (not RAG):** the only vector data here is `siniestros.descripcion` embeddings, used to fire the FS-13 "similar narratives" signal and to populate the "Narrativas similares" accordion. Not retrieval-augmented generation, not document ingestion.

**Fallback:** if pgvector setup blocks beyond a 2-hr timebox, swap to the `InMemoryNarrativeSimilarity` adapter (numpy cosine over an in-process matrix). Same port. Document the swap in `docs/limitaciones.md`.

**Schema convention:**

```sql
create extension if not exists vector;

create table claim_narratives (
  id            uuid primary key default gen_random_uuid(),
  claim_id      text not null references siniestros(id_siniestro) on delete cascade,
  content       text not null,                              -- siniestros.descripcion
  embedding     vector(384) not null,                       -- matches the chosen model dimension
  created_at    timestamptz not null default now()
);

create index on claim_narratives using hnsw (embedding vector_cosine_ops);
create index on claim_narratives (claim_id);
```

---

## 9. Rules engine convention

The 14 FS signals and 7 RF hard rules are the **product spec**, not implementation detail. The folder structure makes that explicit.

- **One file per rule.** `app/domain/rules/signals/FS_07_recurrent_provider.py` defines the `FS_07_RecurrentProvider` class implementing `FraudRule`. Same for hard rules under `hard/`.
- **`FraudRule` is a Protocol** with one method: `evaluate(claim, context) -> RuleActivation | None`. Return `None` when the rule doesn't fire.
- **`RuleActivation`** fields: `code` (e.g. "FS-07"), `tier_hint` (🟢🟡🔴 — hint, the aggregator decides the final tier), `points` (numeric, 0 for hard rules — they override via `tier_hint`), `evidence` (dict with the variables that made the rule fire).
- **`Aggregator.combine(activations) -> ClaimRiskScore`** sums FS points, applies hard-rule overrides (any RF-01..04 forces 🔴; RF-05..07 enforces ≥ 🟡), maps the additive score to a tier band (root CLAUDE.md §2.1: 🟢 0-40 / 🟡 41-75 / 🔴 76-100).
- **Per-rule point thresholds live in `domain/rules/config.py`** (or YAML alongside it). Never inline numeric thresholds in the rule's `evaluate()` — read them from the config so the team can tune without touching logic.
- **Every rule has a unit test** (`tests/domain/rules/test_FS_07_recurrent_provider.py`) using hand-crafted claim fixtures. Aggregator has its own test for hard-rule precedence.
- **`evidence` payload is what the UI renders** under "Reglas activadas". Be specific — `{"proveedor_id": "P-0042", "casos_observados": 7}` is useful; `{"reason": "recurrent provider"}` is not.

---

## 10. ML / anomaly / similarity adapters

These three subsystems run in `score_claim` after the rules engine and produce **complementary** signals (rules say *what* fired, ML/anomaly/similarity say *how unusual* the case looks overall).

**Supervised ML (`infrastructure/ml/lightgbm_adapter.py`):**
- LightGBM classifier trained offline (`notebooks/02_modelo_fraude.ipynb`) on `etiqueta_fraude_simulada`.
- Model artifact: `data/models/fraud_lgbm.txt` (LightGBM's native text format — `booster.save_model(path)` / `lgb.Booster(model_file=path)`). Loaded once at app startup, cached on the FastAPI app state.
- Per-claim output: `ml_probability ∈ [0, 1]` + `top_factors: list[FactorContribution]` (top-3 by absolute SHAP).
- **The ML probability is NOT added to the rules score.** It's surfaced separately on the detail page so the analyst sees rules vs. model independently.
- Metrics target: AUC-ROC ≥ 0.85 on a 20% holdout. Surface metrics in `notebooks/02_*.ipynb` and `docs/uso_ia.md`.

**Anomaly detection (`infrastructure/anomaly/isolation_forest_adapter.py`):**
- Isolation Forest over the numeric feature space (same features as the supervised model, minus the leakage label).
- Model artifact: `data/models/anomaly_iforest.joblib` (`joblib.dump` / `joblib.load`).
- Per-claim output: `anomaly_score ∈ [-1, 1]` (sklearn convention; lower = more anomalous) + `nearest_normal_claim_id` (for UI contrast).
- Surfaced on the detail page as "Indicador de anomalía".

**Narrative similarity (`infrastructure/vectorstore/pgvector_adapter.py`):**
- Sentence-transformer embeds `siniestros.descripcion` on ingest.
- For each claim, find top-3 most-similar prior claims (cosine, exclude self).
- If top-1 similarity > 0.85, FS-13 fires (with the matched claim as evidence).
- Surfaced as the "Narrativas similares" accordion.

**Common adapter rule:** all three adapters cache their loaded model / encoder / index on the FastAPI app state via the lifespan; no global imports. Model artifacts are only loaded from our own `data/models/` directory — never from user input or untrusted sources.

---

## 11. Claims agent

The LangGraph **`claims_agent`** answers the 12 mandatory NL questions in Spanish (root CLAUDE.md §2.6). It is the single graph in this project. Its shape:

```
[start]
   ↓
[ route ] — intent classifier (LLM call with a small structured schema)
   ↓
   ├── query_claims      → tool: query_claims_tool        (Q1, Q9, Q12)
   ├── explain_case      → tool: get_claim_detail_tool    (Q2)
   ├── aggregate         → tool: aggregate_by_dimension   (Q3, Q4, Q5, Q6, Q8, Q10)
   ├── documents         → tool: missing_documents_tool   (Q7)
   └── summarize         → tool: summarize_critical_tool  (Q11)
   ↓
[ compose ] — final Spanish response with citations + tier badges
   ↓
[end]
```

**State (`ClaimsAgentState`)**:
- `query: str` — the user's NL question.
- `intent: Literal["query_claims","explain_case","aggregate","documents","summarize"]` — set by `route`.
- `tool_results: list[ToolResult]` — accumulated.
- `citations: list[ClaimCitation]` — claim IDs referenced.
- `messages: Annotated[list[Message], add_messages]` — for the LLM context.

**Acceptance:** `tests/agent/test_nl_questions.py` runs the 12 NL questions from §2.6 against the agent and asserts the answer mentions at least one specific claim ID + at least one rule code (when applicable). This is the agent's gate.

---

## 12. Database & migrations

*(Stack locked 2026-05-26 — see design spec §13 amendment log.)*

- **SQLAlchemy 2.0 async + asyncpg driver + Alembic.** No raw SQL DDL files; migrations are autogenerated.
- Declarative models live under `app/infrastructure/db/models/` — **one model per file** (`siniestro.py`, `poliza.py`, …). All inherit from a shared `Base = DeclarativeBase` in `app/infrastructure/db/base.py` with a sane naming convention for indexes/FKs.
- Engine + `async_sessionmaker` live in `app/infrastructure/db/engine.py`. The `get_session()` dependency yields an `AsyncSession`; routes inject it via `Depends(get_session)`.
- **Repositories take `AsyncSession`** and expose typed methods. **No raw SQL outside `repositories/`** and `use_cases/load_dataset.py`.
- **One exception for raw asyncpg:** `use_cases/load_dataset.py` uses asyncpg's `copy_records_to_table` for bulk ingest (SQLAlchemy doesn't expose `COPY` cleanly). That's the only place. The connection is acquired and released within that use case — it doesn't share the pool.
- Alembic config: `alembic/env.py` imports `Base` and all model files so `--autogenerate` sees the full schema. Migrations are committed under `alembic/versions/`.
- Common commands:
  ```bash
  uv run alembic revision --autogenerate -m "msg"
  uv run alembic upgrade head
  uv run alembic downgrade -1
  ```
- `pgvector.sqlalchemy.Vector(384)` is the column type for `claim_narratives.embedding` (§8).

---

## 13. Configuration

```python
# core/config.py
class Settings(BaseSettings):
    # app
    APP_ENV: Literal["dev","test","prod"] = "dev"
    LOG_LEVEL: str = "INFO"
    DEBUG_ENABLED: bool = True   # gates PATCH /claims/{id} fire-test endpoint

    # database
    DATABASE_URL: str            # postgresql+asyncpg://...
    # derived form for raw asyncpg (COPY in load_dataset): strip the +asyncpg suffix
    @property
    def DATABASE_URL_RAW(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    # llm  (OpenAI-only for the hackathon — locked 2026-05-26)
    LLM_PROVIDER: Literal["openai","fake"] = "openai"
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    COMPOSE_MODEL: str | None = None        # per-machine override for the compose phase (faster TTFT)
    MAX_REACT_STEPS: int = 3                 # tool-use iteration cap
    MAX_CONVERSATION_TURNS: int = 8
    OPENAI_API_KEY: SecretStr | None = None

    # voice (OpenAI)
    WHISPER_MODEL: str = "whisper-1"         # speech-to-text (chat voice input)
    TTS_MODEL: str = "gpt-4o-mini-tts"       # text-to-speech (agent voice output)

    # embeddings  (OpenAI default; sentence-transformers as local alternative)
    EMBEDDINGS_PROVIDER: Literal["openai","sentence_transformers"] = "openai"
    EMBEDDINGS_MODEL: str = "text-embedding-3-small"
    EMBEDDINGS_DIM: int = 384

    # vector store
    VECTOR_STORE: Literal["pgvector","in_memory"] = "pgvector"

    # ml
    FRAUD_MODEL_PATH: str = "data/models/fraud_lgbm.txt"
    ANOMALY_MODEL_PATH: str = "data/models/anomaly_iforest.joblib"

    # rules
    RULES_CONFIG_PATH: str = "app/domain/rules/config.yaml"
    SIMILARITY_THRESHOLD_FS13: float = 0.85

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

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

settings = Settings()  # cached
```

- All env vars listed (with descriptions) in `.env.example`.
- **No `os.getenv` anywhere else.** Code reads from `settings`.
- **No hardcoded thresholds** (rule weights, similarity cutoffs, tier bands) in business code — all in config.

---

## 14. Errors & logging

- `core/errors.py` defines:
  ```python
  class AppError(Exception): code: str; status_code: int = 500; message: str
  class NotFound(AppError): status_code = 404
  class ValidationFailed(AppError): status_code = 422
  class ProviderError(AppError): status_code = 502
  class RuleEvaluationError(AppError): status_code = 500
  # ...
  ```
- `main.py` registers exception handlers mapping `AppError` → `JSONResponse({code, message})`.
- **Structured logging (JSON)** with `request_id` correlation injected by middleware.
- **Never `print()`.** Use the project logger.
- **Never log secrets** (API keys, raw claim PII even though synthetic).

---

## 15. Testing

- `pytest` + `pytest-asyncio`. Run with `uv run pytest`.
- **Unit tests** per fraud rule (one test file per FS-NN / RF-NN). The rule's test is its acceptance gate.
- **Aggregator tests** for hard-rule precedence + tier-band correctness.
- **Agent tests** — the 12-NL-questions suite (`tests/agent/test_nl_questions.py`) is the agent's acceptance gate.
- **Integration tests** for repositories against a test Postgres (docker-compose service `postgres-test`).
- **One smoke test per route** that hits the app via `httpx.AsyncClient(app=app)`.
- **Don't chase coverage** during the hackathon. Cover: every rule, the aggregator, the agent's 12 questions, and the golden API path.

---

## 16. Docker & CI

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

## 17. Anti-patterns (do NOT do these)

- ❌ Business logic in routes → move to a use case.
- ❌ Business logic in graph nodes → move to a use case or domain service.
- ❌ Giant agent files → split into per-node files under `agents/<name>/nodes/`.
- ❌ One file containing more than one fraud rule → one file per rule.
- ❌ Inline prompts > 5 lines → move to `app/agents/.../prompts/{name}.v1.md`.
- ❌ `import anthropic` / `import openai` outside `infrastructure/llm/` → use the `LLMProvider` port.
- ❌ Hardcoded model names / rule weights / similarity thresholds → read from `settings` or `config.yaml`.
- ❌ Untyped LLM outputs → use structured outputs + pydantic parsing.
- ❌ Free-form `dict` graph state → use a `TypedDict`.
- ❌ `Any` in public signatures → narrow it.
- ❌ Mutable module-level state → put it on the app via lifespan.
- ❌ Catching bare `Exception` → catch what you can handle; let the global handler do the rest.
- ❌ `os.getenv("X")` outside `core/config.py` → use `settings`.
- ❌ Raw SQL outside `repositories/` → use the repo.
- ❌ Using the word `"fraude"` in any user-visible string without `"posible"` — see §2.
- ❌ Using `pip`, `poetry`, `pipenv`, or editing `requirements.txt` → **`uv` only**.
- ❌ Blocking I/O in async paths → `await` it, or push it to `asyncio.to_thread`.
- ❌ Scaffolding `storage/`, `uploads/`, `rag/`, `memory/`, `router_agent/` — see §3 "Deferred". *(`auth/` was removed from this list 2026-05-26 — it's V0 and in scope.)*
- ❌ `import anthropic` anywhere — we don't ship the SDK. Use the `LLMProvider` port (default `openai_adapter`).
- ❌ Raw `asyncpg.Pool` outside `use_cases/load_dataset.py` — go through SQLAlchemy `AsyncSession`.
- ❌ `os.getenv("X")` outside `core/config.py` — including for `JWT_SECRET`. Hardcoded secrets in source = automatic PR rejection.
- ❌ Loading ML model artifacts from any path other than `data/models/` (or another path explicitly configured in `settings`). Model artifacts are trusted because we trained them; never deserialize from user input.

---

## 18. AI-assistant checklist (Claude Code, Cursor, Copilot)

Before you submit a change, verify:

- [ ] All deps added via `uv add`; `pyproject.toml` and `uv.lock` are both committed.
- [ ] No file > 250 LOC. Agent files split into nodes; rules split one-per-file.
- [ ] Routes are thin; logic lives in use cases.
- [ ] Graph nodes touch ports/use cases only, not repositories or external SDKs directly.
- [ ] Provider SDKs only imported inside `infrastructure/llm/` (or analogous adapters).
- [ ] All LLM "give me X" calls use structured outputs with a pydantic schema.
- [ ] Prompts in `app/agents/.../prompts/`, loaded by id.
- [ ] `ChatStreamEvent` shape matches the frontend's definition. If you changed it, regen frontend types.
- [ ] No JWT or secret in logs.
- [ ] No user-visible string contains `"fraude"` without `"posible"`.
- [ ] Every new fraud rule has a unit test and a config entry.
- [ ] `uv run ruff check && uv run mypy app && uv run pytest -q` all green.
