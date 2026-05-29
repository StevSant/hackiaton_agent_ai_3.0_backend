# Modelo de datos

> Deliverable §14.6 — **tablas, campos y relaciones**.
> Léase junto a [`arquitectura.md`](./arquitectura.md), [`reglas_negocio.md`](./reglas_negocio.md) y [`dataset.md`](./dataset.md).
> Fuente normativa: reto Aseguradora del Sur §6 (datos mínimos requeridos).

Los nombres de campo y tabla están en **español snake_case** porque el contrato de cable y el demo son en español (root CLAUDE.md §2.8). Los modelos pydantic ([`app/schemas/`](../app/schemas/)) y los modelos ORM ([`app/infrastructure/db/models/`](../app/infrastructure/db/models/)) reflejan estas tablas verbatim.

---

## 1. Diagrama ER (alto nivel)

```
                       ┌──────────────────────┐
                       │      asegurados      │ id_asegurado (PK)
                       │   (insureds)         │
                       └──────────────────────┘
                              ▲       ▲
                              │       │
                              │       │ 1..N
                              │       │
                       ┌──────┴──┐  ┌─┴──────────────────┐
                       │ polizas │  │     siniestros      │
                       │         │  │     (claims)        │
                       │ id_poliza│◀─┤ id_poliza (FK)     │
                       │ (PK)    │  │ id_asegurado (FK)   │
                       └─────────┘  │ id_siniestro (PK)   │
                                    └─────────────────────┘
                                            ▲
                                            │ 1..N (cascade)
                                            │
                                ┌───────────┼─────────────────────────┐
                                │           │                         │
                       ┌────────┴───┐  ┌────┴──────────┐  ┌──────────┴──────────┐
                       │ documentos │  │ claim_scores  │  │ claim_narratives    │
                       │            │  │ (1:1 latest)  │  │ (pgvector 384 dim)  │
                       └────────────┘  └───────────────┘  └─────────────────────┘

         ┌────────────────────────────────┐
         │ beneficiarios_proveedores      │  id_proveedor (PK)
         │  (referenced by siniestros.    │  (FK lógica, sin constraint físico
         │   beneficiario, FS-07)         │   porque el spec admite "Taller, clínica,
         │                                │   perito u otro" como texto libre)
         └────────────────────────────────┘
```

Tablas adicionales (workflow / agente):

- **`claim_reviews`** — transiciones de estado (pending → escalated → resolved) por usuario y timestamp.
- **`conversations`** + **`messages`** — historial del agente Centinela IA por usuario (descrita en [`limitaciones.md`](./limitaciones.md) §9).

---

## 2. Tablas

### 2.1 `siniestros` — registro principal de reclamos

ORM: [`app/infrastructure/db/models/siniestro.py`](../app/infrastructure/db/models/siniestro.py) · Pydantic: `ClaimDetail` en [`app/schemas/claim.py`](../app/schemas/claim.py).

| Campo | Tipo | Nullable | Descripción |
|---|---|---|---|
| `id_siniestro` | `varchar(64)` | NO (PK) | Identificador único del siniestro. SHA-1 prefix del archetype, uppercased. |
| `id_poliza` | `varchar(64)` | NO (FK → polizas) | Póliza asociada. |
| `id_asegurado` | `varchar(64)` | NO (FK → asegurados) | Asegurado anónimo. |
| `ramo` | `varchar(120)` | NO | `Vehículos` / `Salud` / `Vida` / `Generales` / `Hogar` / otro. |
| `cobertura` | `varchar(120)` | NO | `Choque` / `Robo` / `Atención médica` / `Incendio` / `Daño` / etc. |
| `fecha_ocurrencia` | `date` | NO | Fecha del evento. |
| `fecha_reporte` | `date` | NO | Fecha de notificación a la aseguradora. |
| `monto_reclamado` | `float` | NO | Valor solicitado por asegurado o proveedor. |
| `monto_estimado` | `float` | SI | Valor estimado por la aseguradora. |
| `monto_pagado` | `float` | SI | Valor pagado, si aplica. |
| `estado` | `varchar(60)` | NO | Uno de: `Reserva` / `Pago Total` / `Pago Parcial` / `Anticipo` / `Negativa` / `Cierre Sin Consecuencia` / `Liquidado`. |
| `sucursal` | `varchar(120)` | NO | Sucursal donde se gestiona. |
| `descripcion` | `text` | NO | Texto libre del reclamo. Embebido en `claim_narratives` (FS-13). |
| `documentos_completos` | `bool` | NO | Indicador sí/no agregado (denormalización para listados rápidos). |
| `beneficiario` | `varchar(128)` | SI | Taller, clínica, perito u otro. Coincide opcionalmente con `beneficiarios_proveedores.id_proveedor`. |
| `dias_desde_inicio_poliza` | `int` | SI | Pre-computado en ingesta (`fecha_ocurrencia - poliza.fecha_inicio`). |
| `dias_desde_fin_poliza` | `int` | SI | Pre-computado (`poliza.fecha_fin - fecha_ocurrencia`). |
| `dias_entre_ocurrencia_reporte` | `int` | SI | Pre-computado (`fecha_reporte - fecha_ocurrencia`). |
| `historial_siniestros_asegurado` | `int` | NO | Conteo en últimos 18 meses del mismo asegurado (denormalización para FS-03). |
| `etiqueta_fraude_simulada` | `int` (0/1) | NO | **Sólo entrenamiento / evaluación**. Nunca se expone en la API ni en la UI (§2.2 del CLAUDE.md raíz). |
| `placa` | `varchar(20)` | SI | Sólo cuando `ramo='Vehículos'`. |
| `chasis` | `varchar(40)` | SI | ″ |
| `motor` | `varchar(40)` | SI | ″ |
| `marca` | `varchar(80)` | SI | ″ |
| `modelo` | `varchar(80)` | SI | ″ |
| `anio` | `int` | SI | ″ (el spec usa `año`; los identificadores Python no admiten `ñ`). |
| `latitude` | `float` | SI | Coordenada WGS84 derivada de la ciudad de la sucursal + jitter determinista (mapa de insights). |
| `longitude` | `float` | SI | ″ |
| `resumen_editado` | `text` | SI | Resumen del siniestro editado manualmente por el analista (migración 0014). |
| `signals` | `jsonb` | NO (default `{}`) | Hechos de señales pre-computados que alimentan el `RuleContext` (migración 0013). |
| `workspace_id` | `uuid` | SI | Multi-tenant (no usado en demo). |

**Índices:** `(id_poliza)`, `(id_asegurado)`, `(workspace_id)`.

**Relaciones:**
- `→ polizas` (N:1) via `id_poliza`.
- `→ asegurados` (N:1) via `id_asegurado`.
- `← documentos` (1:N, cascade delete).
- `← claim_scores` (1:1, cascade).
- `← claim_reviews` (1:1, cascade).
- `← claim_narratives` (1:N, cascade — un siniestro puede tener varios chunks de narrativa).

---

### 2.2 `polizas` — pólizas de seguro

ORM: [`poliza.py`](../app/infrastructure/db/models/poliza.py).

| Campo | Tipo | Nullable | Descripción |
|---|---|---|---|
| `id_poliza` | `varchar(64)` | NO (PK) | Identificador único. |
| `id_asegurado` | `varchar(64)` | NO (FK → asegurados) | Titular de la póliza. |
| `ramo` | `varchar(120)` | NO | Mismo dominio que `siniestros.ramo`. |
| `fecha_inicio` | `date` | NO | Inicio de vigencia. |
| `fecha_fin` | `date` | NO | Fin de vigencia. |
| `prima` | `float` | NO | Prima anual. |
| `suma_asegurada` | `float` | NO | Cobertura máxima. Alimenta FS-14. |
| `deducible` | `float` | NO | Deducible aplicable. |
| `canal_venta` | `varchar(80)` | SI | Agencia / broker / web / call center / etc. |
| `ciudad` | `varchar(100)` | NO | Ciudad de emisión. |
| `estado_poliza` | `varchar(60)` | NO | `Vigente` / `Vencida` / `Cancelada` / etc. |

**Índices:** `(id_asegurado)`.

---

### 2.3 `asegurados` — personas aseguradas (sintéticos)

ORM: [`asegurado.py`](../app/infrastructure/db/models/asegurado.py).

| Campo | Tipo | Nullable | Descripción |
|---|---|---|---|
| `id_asegurado` | `varchar(64)` | NO (PK) | Identificador anónimo. |
| `segmento` | `varchar(80)` | SI | Segmento comercial (Premium / Masivo / Corporativo / …). |
| `antiguedad` | `int` | SI | Años como cliente. |
| `ciudad` | `varchar(100)` | NO | Ciudad de residencia. |
| `num_polizas` | `int` | NO | Número de pólizas activas. |
| `reclamos_ultimos_12_meses` | `int` | NO | Conteo agregado (input para FS-03). |
| `mora_actual` | `bool` | NO | Indicador de mora en primas. |
| `score_cliente_simulado` | `float` | SI | Indicador interno de comportamiento simulado (sólo dataset sintético). |

> Importante: **NO contiene PII** (nombres, cédulas, direcciones). Los identificadores son SHA-1 prefijos. Ver [`limitaciones.md`](./limitaciones.md) §2.

---

### 2.4 `beneficiarios_proveedores` — proveedores y beneficiarios

ORM: [`proveedor.py`](../app/infrastructure/db/models/proveedor.py).

| Campo | Tipo | Nullable | Descripción |
|---|---|---|---|
| `id_proveedor` | `varchar(64)` | NO (PK) | Identificador único. |
| `nombre` | `varchar(160)` | SI | Razón social sintética. |
| `tipo` | `varchar(80)` | NO | `Taller` / `Clínica` / `Perito` / `Beneficiario` / otro. |
| `ciudad` | `varchar(100)` | NO | Ciudad de operación. |
| `reclamos_asociados` | `int` | NO | Conteo agregado de siniestros asociados. |
| `monto_promedio_reclamado` | `float` | NO | Promedio histórico (input para análisis comparativo). |
| `porcentaje_casos_observados` | `float` | NO | Pre-agregado para FS-07 (proveedor recurrente). |
| `antiguedad` | `int` | SI | Meses de operación con la aseguradora. |

> No hay FK física desde `siniestros.beneficiario` porque el spec admite texto libre. El cruce se hace en uso (`FS_07_recurrent_provider`) por nombre/id normalizado.

---

### 2.5 `documentos` — documentos adjuntos al siniestro

ORM: [`documento.py`](../app/infrastructure/db/models/documento.py).

| Campo | Tipo | Nullable | Descripción |
|---|---|---|---|
| `id_documento` | `varchar(64)` | NO (PK) | Identificador único. |
| `id_siniestro` | `varchar(64)` | NO (FK → siniestros, ON DELETE CASCADE) | Siniestro asociado. |
| `tipo_documento` | `varchar(120)` | NO | `Denuncia` / `Factura` / `Informe perito` / `Foto` / etc. |
| `entregado` | `bool` | NO | Si el asegurado entregó el documento. Alimenta FS-08. |
| `legible` | `bool` | NO | Si el documento es legible. |
| `fecha_emision` | `date` | SI | Fecha del documento (cruzada contra `fecha_ocurrencia` para FS-11). |
| `inconsistencia_detectada` | `bool` | NO | Marcado por revisión / OCR. Alimenta FS-11 y RF-02. |
| `observacion` | `text` | SI | Notas adicionales. |
| `storage_path` | `varchar(512)` | SI | Ruta en almacenamiento del archivo subido (`infrastructure/storage/`). |
| `filename` | `varchar(255)` | SI | Nombre original del archivo subido. |
| `content_type` | `varchar(120)` | SI | MIME type del archivo subido. |

> La subida de documentos **sí está implementada** (`POST /claims/{id}/documentos` + bulk + OCR vía visión). El RAG sobre esos documentos es lo que queda deferred.

**Índice:** `(id_siniestro)`.

---

## 3. Tablas auxiliares (no en §6 del reto, propias del prototipo)

### 3.1 `claim_scores` — resultado persistido de `score_claim`

ORM: [`claim_score.py`](../app/infrastructure/db/models/claim_score.py). 1:1 con `siniestros` (último score gana). Sólo columnas relevantes:

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` (PK auto) | — |
| `claim_id` | `varchar(64)` UNIQUE FK | → `siniestros.id_siniestro` |
| `score` | `int` | 0–100 (sólo motor de reglas) |
| `tier` | `varchar(20)` | `verde` / `amarillo` / `rojo` |
| `activations` | `jsonb` | `list[{code, points, tier_hint, evidence}]` |
| `ml_probability` | `float` SI | `[0, 1]` o `null` |
| `ml_factors` | `jsonb` | `list[{feature, shap_value, direction}]` |
| `anomaly_score` | `float` SI | rango aprox `[-1, 1]`, más bajo = más anómalo |
| `similar` | `jsonb` | `list[{claim_id, similarity, snippet}]` |
| `narrative_analysis` | `jsonb` SI | Cache del análisis NLP de la narrativa (migración 0015) |
| `panel_analysis` | `jsonb` SI | Resultado del panel multiagente: veredictos + refutaciones + consenso (migración 0016, advisory) |
| `computed_at` | `timestamptz` | Marca de tiempo del cómputo |

### 3.2 `claim_narratives` — embeddings de narrativas (pgvector)

ORM: [`claim_narrative.py`](../app/infrastructure/db/models/claim_narrative.py).

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `varchar(36)` (PK, uuid4) | — |
| `claim_id` | `varchar(64)` FK | → `siniestros.id_siniestro` (CASCADE) |
| `content` | `text` | Copia de `siniestros.descripcion` |
| `embedding` | `vector(384)` | Por defecto OpenAI `text-embedding-3-small`; alternativa `paraphrase-multilingual-MiniLM-L12-v2` (ambos 384 dim) |
| `created_at` | `timestamptz` | — |

**Índices:** `HNSW (embedding vector_cosine_ops)` + B-tree en `(claim_id)`.

### 3.3 `claim_reviews` — transiciones de workflow

Máquina de **5 estados** (`ReviewStatus`): `pendiente → escalado → en_revision → dictaminado`, con la rama alterna `revisado_sin_escalar`. Transiciones: `escalate` (analista), `take` + `dictamen` (antifraude), `close` (analista), `auto_escalate_rojo` (ingesta). El dictamen lleva `outcome ∈ {confirmado_sospecha, descartado, requiere_mas_info}`. Persiste actor, timestamp y notas por transición. Detalle en backend CLAUDE.md §6b y design spec §6.

### 3.4 `conversations` / `messages` — historial del agente

Detalle y limitaciones conocidas en [`limitaciones.md`](./limitaciones.md) §9.

---

## 4. Mapeo con el spec del reto (§6)

Cada tabla del reto se cumple verbatim:

| Tabla del reto | Tabla implementada | Comentarios |
|---|---|---|
| Siniestros (todos los campos del §6.1) | `siniestros` | ✓ Verbatim. Atributos de vehículo presentes con `anio` (Python no admite `ñ`). |
| Pólizas | `polizas` | ✓ Verbatim. |
| Asegurados sintéticos | `asegurados` | ✓ Verbatim. |
| Beneficiarios / Proveedores | `beneficiarios_proveedores` | ✓ Verbatim. |
| Documentos | `documentos` | ✓ Verbatim + columnas de subida de archivos (`storage_path`, `filename`, `content_type`) ya implementadas. |

---

## 5. Migraciones y generación de tipos

- **Backend:** `uv run alembic revision --autogenerate -m "msg"` → siempre revisar el diff antes de hacer `upgrade head`.
- **Frontend:** después de cualquier cambio en `app/schemas/` o `app/infrastructure/db/models/`, regenerar tipos con `pnpm gen:api` (OpenAPI → `src/app/core/api/generated/schema.ts`, read-only).

Cambios al modelo de datos **siempre** disparan PRs cruzados (root CLAUDE.md §10) — un PR en backend, un PR en frontend, un PR en parent que bumpea ambos submódulos.
