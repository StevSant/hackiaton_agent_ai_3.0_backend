# Uso de IA — V4 (clasificador) + V5 (anomalía)

> Deliverable §2.3.7 — explicación de algoritmo, variables, lógica, métricas y limitaciones.
> Léase junto a [`reglas_negocio.md`](./reglas_negocio.md) y [`limitaciones.md`](./limitaciones.md).

El sistema de puntuación de posible fraude es **híbrido por diseño** (ML + NLP + agentes) — el 40% "Uso de IA y Prototipo" del reto. Opera en **capas independientes** que se muestran al analista por separado:

1. **Motor de reglas (V2 / V3)** — 21 reglas (14 FS escalonadas + 7 RF duras) que producen el `score` aditivo 0-100 y la tier 🟢🟡🔴. Es la única fuente del campo `score` en la API.
2. **Capa de IA supervisada + no supervisada (V4 + V5)** — un clasificador LightGBM y un detector de anomalías IsolationForest que enriquecen la respuesta sin modificar el score de reglas (ver §6 del spec del reto, "Explicabilidad y Ética" — 25% del puntaje).
3. **Capa NLP de similitud narrativa** — embeddings de `siniestros.descripcion` con búsqueda por coseno (pgvector) que alimenta FS-13 / RF-07 y el acordeón "Narrativas similares".
4. **Agente conversacional LangGraph** — responde las 12 preguntas obligatorias del reto en lenguaje natural citando IDs y reglas (ver [`arquitectura.md`](./arquitectura.md) §3.3 y backend CLAUDE.md §11).
5. **Panel multiagente de análisis (V6)** — 4 especialistas que debatan el caso en dos rondas + un moderador que sintetiza el consenso (ver §"Panel multiagente" abajo).

> El score numérico viene **sólo** de la capa 1. Las capas 2-5 son **complementarias y advisory**: enriquecen la explicación, nunca sustituyen al motor de reglas ni al analista humano.

La capa de IA viaja en campos separados de `ClaimRiskScore` / `ClaimDetail`:

| Campo | Origen | Significado |
|---|---|---|
| `ml_probability` | LightGBM (V4) | Probabilidad supervisada [0, 1] |
| `ml_factors`     | SHAP (V4)     | Top-3 features que más mueven la probabilidad |
| `anomaly_score`  | IsolationForest (V5) | Indicador no supervisado — más bajo = más anómalo |
| `nearest_normal_claim_id` | NearestNeighbors (V5 sidecar) | Id del siniestro "normal" más parecido |

---

## V4 — Clasificador LightGBM + SHAP

**Algoritmo:** `LightGBM` binario, objetivo `binary` / métrica `auc`, 500 árboles con early stopping a 25 rondas.

**Entrada:** vector de 23 features producido por `extract_features(claim, ctx)` — única fuente de verdad usada tanto en entrenamiento (`notebooks/_training/`) como en inferencia (`infrastructure/ml/lightgbm_adapter.py`). El listado canónico vive en `app/domain/ml/feature_names.py`.

**Etiqueta:** `etiqueta_fraude_simulada` = 1 cuando el tier final calculado por el motor de reglas es 🔴. Se deriva por archetype y se recalcula tras cada perturbación (sección "Entrenamiento" abajo) para que la etiqueta refleje el tier resultante.

**Selección de features — anti-fuga (data leakage):** se excluyen explícitamente los flags que disparan reglas duras (`es_cobertura_ptxrb` → RF-01, `falsificacion_evidente` → RF-02, `dinamica_imposible` → RF-04, `sin_rastro_tercero` → contribuyente fuerte a FS-10) para que el modelo no aprenda a memorizar el motor de reglas. El modelo aprende patrones más suaves: monto, frecuencias, demoras, completitud documental, similitud narrativa.

**Salida por siniestro:**
- `ml_probability ∈ [0, 1]`
- `top_factors`: 3 features con mayor `|shap_value|` + dirección (`up` empuja riesgo arriba).

**Métricas (medidas — reproducibles con `uv run python -m notebooks._training.train_all`):**

Dataset de entrenamiento: 99 archetypes × 30 perturbaciones = **2.970 filas**, 23 features, tasa de positivos perturbada **0.079** (la jitter empuja muchas variantes por debajo del umbral 🔴, así que la etiqueta queda fuertemente desbalanceada — ver [`limitaciones.md`](./limitaciones.md) §4).

| Métrica | Valor | Nota |
|---|---|---|
| AUC-ROC (holdout 20%) | **0.980** | Capacidad de ranking |
| AUC-ROC (CV 5-fold) | **0.982 ± 0.017** | Headline — la varianza refleja el dataset pequeño |
| AUC-PR (holdout) | **0.971** | Robusta al desbalance |
| Precisión / Recall / F1 @ umbral 0.232 | **1.00 / 0.936 / 0.967** | Umbral óptimo de F1 |
| Matriz de confusión @ 0.232 | TN 547 · FP 0 · FN 3 · TP 44 | Holdout de 594 filas |

**Calibración — caveat importante:** las probabilidades del modelo están comprimidas hacia abajo (min/mediana ≈ 0.068, máx ≈ 0.23) por el desbalance 8% positivo. Con el umbral por defecto de 0.5 el modelo predeciría **todo negativo** (recall 0). Por eso el sistema **no** usa el modelo como clasificador duro: la `ml_probability` se expone como una **opinión complementaria rankeada** junto al score de reglas, no como una decisión binaria. El umbral 0.232 (óptimo de F1) se reporta sólo para caracterizar la separabilidad — en producción el ranking (AUC) es lo que importa, no el corte.

**Persistencia:** formato nativo de LightGBM (`Booster.save_model("data/models/fraud_lgbm.txt")`) — texto inspeccionable, sin serializadores genéricos opacos.

## V5 — IsolationForest + nearest-normal kNN

**Algoritmo principal:** `sklearn.ensemble.IsolationForest`, `n_estimators=200`, `contamination=0.20`. Sobre el mismo vector de features que el clasificador (sin la etiqueta) — el contrato de features se mantiene en lockstep entre entrenamiento e inferencia.

**Sidecar kNN:** `sklearn.neighbors.NearestNeighbors` ajustado sobre el subconjunto `etiqueta_fraude_simulada == 0` (los anclas "normales"). En inferencia, para cada siniestro alto-riesgo, devuelve el id del siniestro normal más cercano en el espacio de features. Esto alimenta el widget "compara con un caso normal" del frontend.

**Salida por siniestro:**
- `anomaly_score` — convención sklearn: **más bajo = más anómalo**, rango aproximado `[-1, 1]`.
- `nearest_normal_claim_id` — id del ancla normal más cercana, o `None` si el sidecar no está cargado.

**Persistencia:** `joblib.dump` (recomendado por sklearn). Los artefactos se cargan exclusivamente desde `data/models/` — nunca desde rutas controladas por el usuario.

## Similitud narrativa (NLP) + embeddings

**Proveedor de embeddings (configurable por port).** Por defecto el sistema usa **OpenAI `text-embedding-3-small`** (`EMBEDDINGS_PROVIDER=openai`, `EMBEDDINGS_MODEL=text-embedding-3-small`, 384 dim) — buena calidad multilingüe sin necesidad de GPU local. La alternativa local es **`sentence-transformers`** con `paraphrase-multilingual-MiniLM-L12-v2` (también 384 dim), seleccionable vía `EMBEDDINGS_PROVIDER=sentence_transformers` sin tocar código (`EmbeddingsProvider` port). La dimensión del vector (`vector(384)` en `claim_narratives`) se mantiene igual en ambos.

**Uso.** Las narrativas se embeben **en la ingesta** (no en runtime) y se indexan en `claim_narratives` con HNSW coseno. Para cada siniestro se buscan las narrativas más cercanas (excluyendo la propia):
- similitud `> 0.85` → dispara **FS-13** (clon) y se muestra en "Narrativas similares".
- similitud `≥ 0.98` → dispara **RF-07** (narrativa idéntica → piso amarillo).

**Análisis NLP de narrativa (cache).** Al abrir un siniestro se ejecuta un análisis NLP de la descripción que se cachea en `claim_scores.narrative_analysis` (migración 0015). Abrir un siniestro **no tiene efectos secundarios** sobre el workflow (no escala solo).

## Panel multiagente de análisis (V6)

Capa de IA que pone a **cuatro especialistas LLM a debatir el caso** y un moderador a sintetizar — el componente más visible del eje "agentes que razonan en lenguaje natural" (40% del reto).

**Orquestación:** `app/use_cases/analyze_panel/` + `app/agents/fraud_panel/` (roster + prompts por especialista). Endpoint `POST /api/v1/claims/{id}/panel` (SSE).

**Los 4 especialistas** (cada uno recibe una *rebanada* de datos enfocada, no el caso entero):

| Especialista | Lente | Insumo |
|---|---|---|
| Analista de Reglas | `reglas` | activaciones FS/RF + tier |
| Analista de ML/Anomalía | `ml` | `ml_probability` + SHAP top-3 + `anomaly_score` |
| Analista de Narrativa | `narrativa` | `descripcion` + narrativas similares |
| Analista de Docs/Red | `documentos_red` | completitud documental + stats del proveedor |

**Flujo:** Ronda 1 (cada especialista emite un veredicto estructurado) → Ronda 2 (cada uno reacciona a los veredictos de los demás) → Moderador (consenso). Eventos SSE: `token · verdict · rebuttal · consensus · error · done` (`PanelStreamEvent`).

**Persistencia:** el resultado completo (veredictos + refutaciones + texto del moderador + consenso) se guarda en `claim_scores.panel_analysis` (JSONB, migración 0016) — **advisory, nunca afecta el `score`**. Cachear evita re-ejecutar el panel en cada apertura.

> Todas las llamadas LLM "dame X" del panel usan **structured outputs con `strict=True`**; sin esa bandera, campos requeridos del esquema se caen silenciosamente.

## Entrenamiento

Pipeline reproducible en `notebooks/_training/`. Dos formas de ejecutar:

```bash
# CLI (la que corre CI / producción)
uv run python -m notebooks._training.train_all

# Notebooks (presentación + métricas + SHAP plots)
uv run jupyter notebook notebooks/02_modelo_fraude.ipynb
uv run jupyter notebook notebooks/03_evaluacion_modelo.ipynb
```

**Cómo se construye el dataset:**

1. Se carga el JSON canónico de 99 archetypes desde `data/synthetic/claims.json`.
2. Cada archetype se perturba 30 veces (jitter ±20% en monto, ±3 días en `fecha_reporte`) → 2.970 filas.
3. Cada variante perturbada es **re-scoreada** por el motor de reglas para que la etiqueta refleje el tier resultante (no la del archetype original). Así una perturbación que cruza un umbral mueve la etiqueta naturalmente.
4. Se materializa `X` en el orden de `FEATURE_NAMES` + `y` binaria + `claim_ids` paralelos.

Los artefactos producidos en `data/models/`:

```
data/models/
├── fraud_lgbm.txt          (~50-200 KB)  — V4
├── anomaly_iforest.joblib  (~100-500 KB) — V5
└── anomaly_knn.joblib      (~50-200 KB)  — V5 sidecar
```

## Integración con la API

El backend carga los tres artefactos una sola vez al arranque (`app/core/lifespan_state.py`) y los expone vía deps a las rutas:

- `GET /claims/{id}` y `POST /claims/{id}/rescore` llaman a `enrich_claim_score(claim, classifier, detector)` después del motor de reglas.
- Si los artefactos no están en disco, las rutas siguen funcionando — los campos ML quedan en `None` / `[]`, y el frontend oculta sus widgets correspondientes.
- `GET /claims` (lista) NO ejecuta ML — el desglose por modelo solo aparece en la página de detalle (decisión costos vs. valor).

`GET /api/v1/status/ai` reporta los flags `fraud_model_present` y `anomaly_model_present` para diagnóstico rápido.

## Por qué la separación rules vs. ML

El reto pondera **25% en explicabilidad y ética**. Mezclar la probabilidad supervisada en el score de reglas significa:

1. Imposible explicar al analista *por qué* el score subió 12 puntos — el modelo es una caja gris.
2. Drift del modelo arrastra al score visible — degrada la trazabilidad sin que nadie lo note.
3. El analista ya no puede ignorar la opinión del modelo cuando no aplica — la decisión humana queda contaminada.

Manteniéndolas separadas: el analista ve `score=72 (amarillo)` + `ml_probability=0.81` + `anomaly_score=-0.34` como tres opiniones independientes. Si las tres coinciden, la confianza es alta. Si discrepan, ya tiene material para investigar.
