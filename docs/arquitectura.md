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
│  auth · claims · agent · panel · imports · documents · reviews · insights  │
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

**Routers expuestos en `app/api/v1/`** (la caja muestra sólo los principales):
`auth` · `claims` · `agent` (ask SSE + transcribe + tts) · `panel` (panel multiagente SSE) ·
`imports` · `documents` · `reviews` (workflow antifraude) · `insights` · `audit` ·
`conversations` (historial del agente) · `asegurados` · `network` (proveedores) ·
`rules` (catálogo + config + cambios) · `reports` · `status` (`/status/ai`) · `health`.

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

### 3.3-bis Panel multiagente de análisis (capa de IA adicional)

```
POST /api/v1/claims/{id}/panel  ──▶ analyze_panel use case
                                       │
                                       ▼
                          agents/fraud_panel — 4 especialistas
                            ├─ Analista de Reglas     (reglas + tier)
                            ├─ Analista de ML/Anomalía (ml_probability + SHAP + anomaly)
                            ├─ Analista de Narrativa   (descripción + similitud)
                            └─ Analista de Docs/Red    (documentos + proveedor)
                                       │
                          R1: cada especialista emite veredicto estructurado
                          R2: cada uno reacciona a los veredictos de los demás
                          Moderador: sintetiza → consenso
                                       ▼
                       text/event-stream (PanelStreamEvent):
                         token · verdict · rebuttal · consensus · error · done
                                       ▼
                       persistido en claim_scores.panel_analysis (JSONB)
```

- Es una **capa de IA complementaria y advisory**: nunca modifica el `score` de reglas — sólo enriquece la explicación (cubre el 40% "Uso de IA" del reto: ML + NLP + agentes que debaten en lenguaje natural).
- Cada especialista analiza una **rebanada de datos enfocada** (`slice_fn` en `agents/fraud_panel/roster.py`), evita que un solo prompt vea todo el caso y reduce alucinación.
- El resultado se cachea en `claim_scores.panel_analysis` (migración 0016) para auditoría y para no re-ejecutar el panel en cada apertura.
- Visualizado en el frontend en `/fraud-panel` (debate en vivo) y embebido en el detalle del siniestro.

### 3.4 Workflow de revisión (CU-03 / CU-04)

```
analista visualiza /claims (triage)
   │
   ▼
abre /claims/{id} (CU-04 — explicación)
   │
   ▼
máquina de 5 estados (`ReviewStatus`):
   pendiente → escalado → en_revision → dictaminado
                              (alternativa: revisado_sin_escalar)

   ├─ analista   → POST /claims/{id}/escalate   (pendiente → escalado)
   │             → POST /claims/{id}/close       (revisado sin escalar)
   ├─ antifraude → POST /claims/{id}/take         (escalado → en_revision)
   │             → POST /claims/{id}/dictamen     (en_revision → dictaminado)
   │                outcome ∈ {confirmado_sospecha, descartado, requiere_mas_info}
   └─ debug      → PATCH /claims/{id}             (gated DEBUG_ENABLED)
```

- RBAC con dos roles (`analista`, `antifraude`) gateado por `require_role()` en el router. Detalle en backend CLAUDE.md §6b.
- Los siniestros 🔴 se auto-escalan en la ingesta (`auto_escalate_rojo`); **abrir** un siniestro no tiene efectos secundarios (no escala solo).
- Cada transición se persiste en `claim_reviews` con actor + timestamp + nota — la UI muestra la línea de tiempo. Cola del antifraude en `GET /antifraude/inbox`, histórico en `GET /antifraude/historico`.

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
| Embeddings | OpenAI `text-embedding-3-small` (384-dim) por defecto; `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`) como alternativa local vía port | Calidad multilingüe sin GPU local |
| Voz | OpenAI Whisper (`whisper-1`) entrada · TTS (`gpt-4o-mini-tts`) salida | Chat por voz bidireccional con el agente |
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
- Pipeline de ingesta RAG (la **subida de archivos / documentos sí está implementada** — `infrastructure/storage/`, `use_cases/import_claims/`, `upload_claim_document*`; lo deferred es el RAG sobre esos documentos).
- Long-term memory del agente.
- Router agent multi-task.
- Detección de drift en runtime.
- Pipeline de reentrenamiento automatizado.

> **Aterrizó durante el hackathon y ahora es first-class** (originalmente deferred): subida de documentos + import de siniestros, transcripción de voz Whisper + TTS, historial de conversaciones, gráficas ECharts generadas por el agente, y el **panel multiagente de análisis** (§3.3-bis).

Los `Protocol` correspondientes (`LLMProvider`, `EmbeddingsProvider`, `NarrativeSimilarity`, `FraudClassifier`, `AnomalyDetector`, `AuthVerifier`, `SpeechTranscriber`) están definidos para permitir extensión post-hackathon sin reescritura.

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
