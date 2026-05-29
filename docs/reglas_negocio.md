# Rúbrica de alertas — reglas de negocio

> Deliverable §14.8 — **rúbrica de alertas: reglas o criterios usados para generar alertas**.
> Léase junto a [`uso_ia.md`](./uso_ia.md), [`modelo_datos.md`](./modelo_datos.md) y [`limitaciones.md`](./limitaciones.md).
> Fuente normativa: reto Aseguradora del Sur §7, §8 y §13.

El motor de reglas es la **única fuente** del campo `score` (0–100) y del semáforo `tier` (🟢🟡🔴) que recibe el analista. Combina dos familias de reglas:

| Familia | Codigos | Naturaleza | Efecto sobre score |
|---|---|---|---|
| **Señales escalonadas** (FS) | FS-01 … FS-14 | Aditivas, con bandas de puntos | Suman al score (cap 100) |
| **Reglas duras** (RF) | RF-01 … RF-07 | Sobreescriben el `tier` final | 0 puntos; cambian el semáforo |

Cada regla vive en un archivo bajo [`app/domain/rules/signals/`](../app/domain/rules/signals) (FS) o [`app/domain/rules/hard/`](../app/domain/rules/hard) (RF). Los umbrales numéricos viven en [`app/domain/rules/config.yaml`](../app/domain/rules/config.yaml) y se pueden ajustar **sin tocar código**.

---

## 1. Bandas del semáforo (§13 del reto)

Mapeo aditivo `score → tier` (configurable en `config.yaml::tier_bands`):

| Rango | Tier | Acción sugerida |
|---|---|---|
| **0 – 40** | 🟢 verde | Flujo normal |
| **41 – 75** | 🟡 amarillo | Escala a Unidad Antifraude para revisión documental |
| **76 – 100** | 🔴 rojo | Escala a Unidad Antifraude para revisión especializada de campo |

El semáforo final = `max(score_to_tier(score), hard_floor)` donde `hard_floor` lo determinan las reglas RF (ver §3).

---

## 2. Señales escalonadas (FS-01 … FS-14)

Todas las señales producen una `RuleActivation` con `code`, `points`, `tier_hint` y un objeto `evidence` con las variables exactas que dispararon la regla. La evidencia es lo que se renderiza en la UI bajo "Reglas activadas" (root CLAUDE.md §11).

### FS-01 — Reclamo cercano al borde de vigencia · máx **8 pts**

- **Disparador:** la fecha de ocurrencia está cerca del inicio o fin de la póliza.
- **Bandas (`config.yaml::FS_01`):**
  - `≤ 10 días` → **8 pts**
  - `11–30 días` → **4 pts**
  - `> 30 días` → no dispara
- **Variables del contexto:** `dias_desde_inicio_poliza`, `dias_desde_fin_poliza` (recalculadas en `RuleContext.from_claim` desde las fechas reales de la póliza).
- **Evidencia:** `{ dias_desde_inicio_poliza, dias_desde_fin_poliza, banda }`.

### FS-02 — Demora en denuncia de robo · máx **8 pts**

- **Disparador:** sólo aplica cuando la cobertura involucra robo (`ctx.es_robo`).
- **Bandas (`config.yaml::FS_02`):**
  - `> 48 horas` → **8 pts**
  - `24–48 horas` → **4 pts**
  - `< 24 horas` → no dispara
- **Variable:** `demora_denuncia_horas` (derivada de `fecha_reporte - fecha_ocurrencia`).
- **Evidencia:** `{ demora_horas, cobertura }`.

### FS-03 — Alta frecuencia de reclamos por asegurado · máx **8 pts**

- **Disparador:** múltiples siniestros del mismo `id_asegurado` en los últimos 18 meses.
- **Bandas (`config.yaml::FS_03`):**
  - `≥ 3 siniestros` → **8 pts**
  - `= 2 siniestros` → **4 pts**
  - `0–1` → no dispara
- **Variable:** `historial_siniestros_asegurado` (precomputada en ingesta o agregada por `score_claim`).
- **Evidencia:** `{ historial }`.

### FS-04 — Alta frecuencia de reclamos por vehículo · máx **6 pts**

- **Disparador:** múltiples siniestros sobre el mismo vehículo (`placa`+`chasis`) en 18 meses.
- **Bandas (`config.yaml::FS_04`):** `≥ 3 → 6 pts`, `2 → 3 pts`.
- **Variable:** `frecuencia_vehiculo`.

### FS-05 — Alta frecuencia de conductor · máx **8 pts**

- **Disparador:** mismo conductor en múltiples siniestros en 18 meses.
- **Bandas (`config.yaml::FS_05`):** `≥ 3 → 8 pts`, `2 → 4 pts`.

### FS-06 — Alta frecuencia de eventos sólo RC · máx **6 pts**

- **Disparador:** asegurado con varios eventos previos donde sólo se afecta Responsabilidad Civil.
- **Bandas (`config.yaml::FS_06`):** `> 2 eventos RC → 6 pts`, `1 → 3 pts`.

### FS-07 — Beneficiario / proveedor recurrente · máx **10 pts**

- **Disparadores (orden de prioridad):**
  1. Proveedor o beneficiario aparece en **lista restrictiva** → **10 pts**.
  2. Proveedor asociado a `> 2` casos observados (no en lista) → **5 pts**.
- **Variables:** `proveedor_en_lista_restrictiva`, `beneficiario_en_lista_restrictiva`, `proveedor_casos_observados`.
- **Evidencia:** `{ proveedor_id, en_lista_restrictiva, casos_observados }`.

### FS-08 — Documentos incompletos · **4 pts** (fijo)

- **Disparador:** falta al menos un documento legal obligatorio (`Documento.entregado = false` en cualquier documento requerido).
- **Variable:** `documentos_incompletos` (booleano).

### FS-09 — Dinámica sospechosa · máx **6 pts**

- **Disparadores:**
  - Narrativa ilógica vs. tipo de impacto → **6 pts**
  - Accidente múltiple de madrugada → **3 pts**
- **Variables:** `narrativa_ilógica`, `evento_medianoche`.

### FS-10 — Daño severo sin rastro de tercero · **6 pts** (fijo)

- **Disparador:** siniestros donde el vehículo asegurado está afectado pero el tercero huyó o no existen cámaras.
- **Variable:** `sin_rastro_tercero`.

### FS-11 — Documentos inconsistentes · máx **10 pts**

- **Disparadores:**
  - Alteración confirmada o fechas de factura previas al evento → **10 pts**
  - Inconsistencia sospechada (sin confirmar) → **5 pts** (banda interna de gracia)
- **Variable:** `inconsistencia_documental`.

### FS-12 — Reporte tardío · máx **5 pts**

- **Bandas (`config.yaml::FS_12`):**
  - `> 7 días` → **5 pts**
  - `4–7 días` → **3 pts**
  - `≤ 3 días` → no dispara
- **Variable:** `dias_entre_ocurrencia_reporte`.

### FS-13 — Narrativas similares · máx **8 pts**

- **Mecanismo:** la capa de similitud narrativa (`infrastructure/vectorstore/pgvector_adapter.py`) busca la narrativa más cercana al `siniestros.descripcion` actual usando embeddings (por defecto OpenAI `text-embedding-3-small`, 384 dim; alternativa local `paraphrase-multilingual-MiniLM-L12-v2`) + índice HNSW cosine.
- **Bandas (`config.yaml::FS_13`):**
  - `similitud > 0.85` → **8 pts** (clon)
  - `0.70 – 0.84` → **4 pts** (parecido)
  - `< 0.70` → no dispara
- **Evidencia:** `{ matched_claim_id, similarity, snippet }`.

### FS-14 — Monto cercano o superior a suma asegurada · **5 pts**

- **Disparadores (OR lógico):**
  - `monto_reclamado / suma_asegurada ≥ 0.95` → fires
  - `monto_reclamado > 1.50 × promedio_reparacion_clase` → fires
- **Variables:** `monto_vs_suma_pct`, `monto_vs_reparacion_avg_pct`.

---

## 3. Reglas duras (RF-01 … RF-07)

Las reglas duras **no suman puntos** — sobreescriben el `tier` final. Su `RuleActivation.points = 0` pero su `tier_hint` se procesa en [`app/domain/rules/aggregator.py`](../app/domain/rules/aggregator.py):

- **RF-01 … RF-04** → fuerzan `tier = rojo` aunque el score esté en banda verde.
- **RF-05 … RF-07** → fijan **piso** en `amarillo` (suben desde verde, no bajan rojo).

| Código | Nombre | Disparador | Efecto |
|---|---|---|---|
| **RF-01** | Cobertura Pérdida Total por Robo (PTxRB) | Cobertura del siniestro coincide con `Pérdida Total por Robo` / `PTxRB` / `Robo Total` (lista en `config.yaml::RF_01.coberturas_ptxrb`) | → **rojo** |
| **RF-02** | Falsificación o adulteración documental evidente | `ctx.falsificacion_evidente = true` (marcado por revisión documental o por inconsistencia confirmada en un documento clave) | → **rojo** |
| **RF-03** | Coincidencia exacta con lista restrictiva | Asegurado, beneficiario o proveedor aparece en lista restrictiva (`*_en_lista_restrictiva`) | → **rojo** |
| **RF-04** | Dinámica del accidente físicamente imposible | `ctx.dinamica_imposible = true` (declarado por el peritaje o detectado por análisis de la narrativa) | → **rojo** |
| **RF-05** | Siniestro extremo al borde de vigencia (< 48 hrs) | `dias_desde_inicio_poliza < 2` (configurable en `config.yaml::RF_05.threshold_hours`) | → piso **amarillo** |
| **RF-06** | Demora atípica en denuncia de robo (> 4 días) | `es_robo = true` y `dias_entre_ocurrencia_reporte > 4` | → piso **amarillo** |
| **RF-07** | Narrativa idéntica (clonada) | Similitud narrativa `≥ 0.98` con cualquier otro siniestro (umbral en `config.yaml::RF_07.threshold_similarity`) | → piso **amarillo** |

**Relación FS-13 ↔ RF-07:** la misma señal de similitud alimenta ambas reglas. FS-13 suma puntos (banda 0.70–0.85+); RF-07 fuerza piso amarillo cuando la similitud cruza 0.98 (= prácticamente idéntica).

---

## 4. Algoritmo de agregación (orquestador)

[`app/domain/rules/aggregator.py::aggregate(activations)`](../app/domain/rules/aggregator.py):

1. **Sumar** todos los puntos de activaciones cuyo `code` comienza con `FS-`. Cap a 100.
2. Derivar `tier_base = score_to_tier(score)` con las bandas de §1.
3. Aplicar **overrides duros**:
   - Si alguna activación tiene `code ∈ {RF-01, RF-02, RF-03, RF-04}` → `tier = rojo`.
   - Si no, y alguna activación tiene `code ∈ {RF-05, RF-06, RF-07}` → `tier = max(tier_base, amarillo)`.
4. Devolver `(score, tier)`.

`score` y `tier` viajan en `ClaimRiskScore` junto al listado completo de `activations` (lo que el frontend renderiza en el desglose "Reglas activadas").

---

## 5. Cómo extender el catálogo

1. Crear un archivo nuevo en `signals/FS_NN_<nombre>.py` o `hard/RF_NN_<nombre>.py`.
2. Implementar el `Protocol` `FraudRule` ([`ports.py`](../app/domain/rules/ports.py)) — método `evaluate(claim, ctx) -> RuleActivation | None`.
3. Declarar `META: RuleMeta` con `code`, `name`, `tier_hint`, `short_description`, `what_triggers`, `max_points`.
4. Registrar la instancia en [`catalog.py::_ALL_RULES`](../app/domain/rules/catalog.py).
5. Añadir bloque en `config.yaml` con los umbrales numéricos.
6. Añadir test unitario en `tests/domain/rules/`.
7. Si la regla necesita una variable nueva del contexto, extender [`RuleContext`](../app/domain/rules/context.py) con un default seguro (no-fire) para no romper rutas existentes.

**Nunca** inlinear umbrales numéricos en `evaluate()` — siempre `rule_cfg("FS_NN")` desde el loader (root CLAUDE.md §9, anti-pattern §17).

---

## 6. Trazabilidad (25% del puntaje del reto)

Cada `RuleActivation` lleva su propia `evidence` específica de la regla. La UI del analista (`ClaimDetailPage` → `AlertsList`) renderiza la lista ordenada por puntos descendentes, con código + nombre + severidad + evidencia + puntos. Esto cubre directamente el criterio de **explicabilidad y trazabilidad** (§18 del reto, 15%; §22 5-Excepcional Explicabilidad y Ética, 25%).

La fuente única para preguntar `"¿por qué este siniestro está en rojo?"` (Q2 del agente, §2.6 del CLAUDE.md raíz) es `ClaimRiskScore.activations` + `ClaimRiskScore.ml_factors` + `ClaimRiskScore.similar`. El agente nunca inventa reglas — sólo enumera las que el motor disparó.
