# Arquitectura

> Deliverable §14.5 — **diagrama o explicación técnica**.
> Léase junto a [`modelo_datos.md`](./modelo_datos.md), [`reglas_negocio.md`](./reglas_negocio.md) y [`uso_ia.md`](./uso_ia.md).

Sistema de **detección de posibles fraudes en siniestros** (reto Aseguradora del Sur). Mantenemos un único principio rector: **alertamos, no acusamos** — toda salida es una recomendación para revisión humana (§2.10 del CLAUDE.md raíz).

---

## 1. Vista de bloques

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTE (Angular)                              │
│  Triage dashboard · Detalle del siniestro · Chat con el agente · Reportes  │
└────────────────────────────────────────────────────────────────────────────┘
            ▲                              ▲                        ▲
            │ REST (OpenAPI)               │ SSE (text/event-stream)│ REST
            │                              │                        │
┌───────────┴──────────────────────────────┴────────────────────────┴────────┐
│                           API FastAPI (api/v1/*)                            │
│  auth · claims · agent · imports · documents · insights · audit · reviews  │
└────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              USE CASES (orchestrators)                      │
│  score_claim · ask_agent · list_claims · escalate_claim · resolve_claim ·  │
│  load_dataset · generate_report                                             │
└────────────────────────────────────────────────────────────────────────────┘
            │                       │                       │
            ▼                       ▼                       ▼
┌──────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│   DOMAIN (puro)  │   │   AGENTS (LangGraph) │   │   REPOSITORIES (SA)  │
│  rules · ml port │   │  claims_agent/graph  │   │  claims · polizas    │
│  anomaly port    │   │  nodes · tools ·     │   │  asegurados ·        │
│  similarity port │   │  prompts             │   │  proveedores · docs  │
└──────────────────┘   └──────────────────────┘   └──────────────────────┘
                                  │                            │
                                  ▼                            ▼
                       ┌──────────────────────┐    ┌──────────────────────┐
                       │   INFRASTRUCTURE     │    │   PostgreSQL +       │
                       │ llm · embeddings ·   │◀──▶│   pgvector           │
                       │ vectorstore · ml ·   │    │ (siniestros, ...,    │
                       │ anomaly · auth · db  │    │  claim_narratives)   │
                       └──────────────────────┘    └──────────────────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │   OpenAI gpt-4o-mini │
                       │  (única dependencia  │
                       │  externa de runtime) │
                       └──────────────────────┘
```

---

## 2. Capas y dirección de dependencias

```
api ──▶ use_cases ──▶ domain
              │
              ├──▶ repositories ──▶ infrastructure/db
              ├──▶ agents ──▶ infrastructure/llm + tools
              └──▶ infrastructure/{ml,anomaly,vectorstore,embeddings} (vía ports)
```

- **`domain/`** no importa de ningún otro módulo. Es lógica pura (reglas, tipos de valor).
- **`api/`** no importa directamente de `infrastructure/`; todo pasa por `api/deps.py` (factorías).
- **`agents/`** llama use cases o ports, nunca repositorios.
- **`infrastructure/`** implementa los `Protocol` definidos en `domain/.../ports.py`.

Este patrón **ports & adapters** permite cambiar de proveedor (LLM, vector store, ML, anomaly) tocando **un solo archivo** por componente.

---

## 3. Flujo end-to-end de un siniestro

### 3.1 Ingesta (CU-01)

```
CSV / JSON ──▶ POST /api/v1/imports ──▶ ImportClaims use case ──▶ asyncpg COPY
   │                                          │
   │                                          ▼
   │                              SQLAlchemy bulk insert: siniestros,
   │                              polizas, asegurados, proveedores, docs
   ▼
Validación pydantic (schemas/claim.py) + normalización fechas/montos
```

- El loader vive en [`app/use_cases/load_dataset/`](../app/use_cases/load_dataset/) y es la **única** ruta que usa raw asyncpg (`COPY` no expuesto en SQLAlchemy).
- Las narrativas (`siniestros.descripcion`) se embeben en `claim_narratives` con `sentence-transformers` durante la ingesta (no en runtime).

### 3.2 Scoring (CU-02)

```
GET /api/v1/claims/{id} ──▶ get_claim_detail
                              │
                              ▼
                       score_claim use case
                              │
            ┌─────────────────┼────────────────────┐
            ▼                 ▼                    ▼
       Rules engine     ML adapter        Anomaly adapter
       (21 reglas)      (LightGBM+SHAP)   (IsolationForest+kNN)
            │                 │                    │
            └────┬────────────┴─────────┬──────────┘
                 ▼                      ▼
        ClaimRiskScore           Similarity adapter
        { score, tier,           (pgvector cosine)
          activations,                   │
          ml_probability,                ▼
          ml_factors,            list[SimilarClaim]
          anomaly_score,
          similar }
```

- Las cuatro capas (reglas, ML, anomalía, similitud) son **independientes**: cada una viaja en su propio campo del `ClaimRiskScore`. El `score` numérico viene **sólo** del motor de reglas — la probabilidad ML y la rareza anómala se muestran como opiniones complementarias (ver [`uso_ia.md`](./uso_ia.md) §"Por qué la separación").
- Si una capa falla o el artefacto no está cargado, los campos correspondientes quedan en `None` / `[]` y la UI los oculta — sin romper la respuesta.

### 3.3 Agente conversacional (CU-05)

```
POST /api/v1/agent/ask  ──▶ ask_agent use case
   {query, context}             │
                                ▼
                       LangGraph claims_agent
                        START → route (LLM intent classifier)
                              ├─▶ query_claims tool   (Q1, Q9, Q12)
                              ├─▶ get_claim_detail    (Q2)
                              ├─▶ aggregate_by_dim    (Q3-Q6, Q8, Q10)
                              ├─▶ missing_documents   (Q7)
                              ├─▶ summarize_critical  (Q11)
                              └─▶ compose (Spanish renderer)
                                ▼
                          END → SSE stream
                                ▼
                   text/event-stream (ChatStreamEvent):
                     token · tool_call · tool_result ·
                     agent_step · error · done
```

- El backend traduce los eventos crudos de LangGraph (`astream_events v2`) al shape `ChatStreamEvent` (contrato compartido frontend ↔ backend, root CLAUDE.md §5).
- El agente nunca consulta la BD directamente — todas las herramientas internamente llaman use cases del backend.
- Cada respuesta del agente cita IDs de siniestros y códigos de reglas activadas → cumple §22 del reto (trazabilidad como criterio de evaluación).

### 3.4 Workflow de revisión (CU-03 / CU-04)

```
analista visualiza /claims (triage)
   │
   ▼
abre /claims/{id} (CU-04 — explicación)
   │
   ▼
opciones según rol:
   ├─ analista → POST /claims/{id}/escalate     (pending → escalated)
   └─ antifraude → POST /claims/{id}/resolve    (escalated → resolved)
                 → PATCH /claims/{id} (debug, gated DEBUG_ENABLED)
```

- RBAC con dos roles (`analista`, `antifraude`) gateado por `require_role()` en el router. Detalle en backend CLAUDE.md §6b.
- Cada transición de estado se persiste en `claim_reviews` (tabla aparte) — la UI puede mostrar el historial.

### 3.5 Reporte ejecutivo (CU-06)

`GET /api/v1/insights` agrega:
- Top-N siniestros por score.
- Distribución por ramo, ciudad, proveedor.
- Tendencia 30d de % rojo.
- Top-K anomalías por `anomaly_score`.

Se renderiza en la página `/insights` (executive dashboard) + exportable a CSV.

---

## 4. Stack técnico (resumen)

| Capa | Tecnología | Por qué |
|---|---|---|
| Lenguaje | Python 3.12+ | Tipado moderno, ecosistema ML |
| HTTP | FastAPI | Async, OpenAPI auto, validación pydantic |
| Orquestación de agentes | LangGraph | Grafos explícitos, streaming nativo |
| LLM | OpenAI `gpt-4o-mini` (via port) | Costo bajo, latencia aceptable para 12 NL questions |
| Embeddings | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim) | Soporta español |
| BD relacional + vectorial | PostgreSQL + pgvector (HNSW) | Un solo datastore — joins relacional+vectorial en un SQL |
| ORM + migraciones | SQLAlchemy 2.0 async + asyncpg + Alembic | Async end-to-end |
| ML supervisado | LightGBM + SHAP | Rápido, explicable (top-3 factores) |
| Anomalía | scikit-learn IsolationForest + NearestNeighbors sidecar | "Compara con el caso normal más cercano" |
| Auth | JWT local (PyJWT + bcrypt) | V0 para hackathon; port preservado para Supabase post-hackathon |
| Empaquetado | `uv` (lock determinístico) | Reproducibilidad CI/Docker |
| Despliegue | Docker multi-stage + docker-compose | Self-contained (app + Postgres+pgvector) |

---

## 5. Decisiones de diseño clave

### 5.1 Por qué pgvector y no un vector store separado

Postgres ya es el system of record (siniestros, pólizas, etc.). Embebimos las narrativas (`claim_narratives.embedding`) en la **misma base** — sin segundo datastore que desplegar, monitorear, respaldar o sincronizar. Permite además consultas que mezclan relacional + vectorial en un solo SQL (ej. "los 3 siniestros más similares al X **excluyendo** los > 18 meses").

### 5.2 Por qué rules ≠ ML

La probabilidad supervisada **no se mezcla** con el score aditivo de reglas. Razones (detalle en [`uso_ia.md`](./uso_ia.md) §"Por qué la separación"):

1. Mezclar imposibilita explicar al analista por qué el score subió 12 puntos — el modelo es una caja gris.
2. Drift del modelo arrastra al score visible — degrada trazabilidad sin que nadie lo note.
3. El analista pierde la opción de ignorar al modelo cuando no aplica.

Manteniéndolos separados: el analista ve `score=72` + `ml_prob=0.81` + `anomaly=-0.34` como tres opiniones independientes. Si las tres coinciden, alta confianza. Si discrepan, ya tiene material para investigar.

### 5.3 Por qué SSE y no WebSockets

El stream del agente es **unidireccional** (server → client, tokens y eventos). HTTP/SSE es suficiente, juega bien con proxies y CDN, y no requiere un stack adicional. WebSockets aportarían complejidad sin valor para este caso.

### 5.4 Por qué un archivo por regla

Cada FS / RF es **producto**, no implementación: el reto las califica una por una. Un archivo por regla:
- Hace cada regla testeable en aislamiento.
- Permite revisar PRs regla por regla.
- Cada regla incluye su `META` (catálogo) — la UI puede pintar el listado completo (página `/alerts`).

### 5.5 Por qué `uv` y no pip/poetry

- Lockfile reproducible (`uv.lock`) — el CI falla si el lockfile está desincronizado.
- Velocidad: instalación 10× más rápida (cache local).
- Dockerfile multi-stage usa `uv sync --frozen --no-dev` — imagen final mínima.

---

## 6. Lo que **NO** está en runtime (deferred — §11 del design spec)

Componentes deliberadamente fuera de scope para esta entrega:

- Supabase Auth (usamos JWT local).
- File-upload + RAG ingestion pipeline.
- Long-term memory del agente.
- Router agent multi-task.
- Detección de drift en runtime.
- Pipeline de reentrenamiento automatizado.

Los `Protocol` correspondientes (`LLMProvider`, `EmbeddingsProvider`, `NarrativeSimilarity`, `FraudClassifier`, `AnomalyDetector`, `AuthVerifier`) están definidos para permitir extensión post-hackathon sin reescritura.

---

## 7. Modo de ejecución local

```bash
# 1. Levantar Postgres+pgvector
docker compose up -d db

# 2. Aplicar migraciones
uv run alembic upgrade head

# 3. Generar y cargar dataset sintético
uv run python scripts/generate_dataset.py
LOAD_DATASET_ON_STARTUP=true uv run uvicorn app.main:app --reload

# 4. Frontend (otro terminal)
cd ../hackiaton_agent_ai_3.0_frontend
pnpm install && pnpm gen:api && pnpm dev
```

API en `http://localhost:8000/docs` · UI en `http://localhost:4200`.
