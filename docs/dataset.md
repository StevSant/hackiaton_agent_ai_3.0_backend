# Dataset sintético — Centinela IA

> Deliverable §14.3 — **dataset (sintético o público) con origen y estructura explicados**.
> Léase junto a [`modelo_datos.md`](./modelo_datos.md) y [`uso_ia.md`](./uso_ia.md).

## Origen

100% sintético; sin PII real (§2.10 del reto).
Generado de forma **determinística** a partir de `app/use_cases/generate_dataset/_archetypes.py`
(99 *archetypes* hand-crafted) vía `scripts/generate_dataset.py`
(o `app.use_cases.generate_dataset.generate_and_save`).

Al ser determinístico, regenerar produce exactamente el mismo dataset — clave para
reproducir métricas del modelo y comportamiento del demo.

## Archivos (`data/synthetic/`)

| Archivo | Filas | Descripción |
|------|------|-------------|
| `siniestros.csv` | 99 | Tabla principal (§2.8) |
| `polizas.csv` | 99 | Una póliza por siniestro (aproximación) |
| `asegurados.csv` | 99 | Un asegurado por siniestro |
| `beneficiarios_proveedores.csv` | 54 | Proveedores únicos entre los siniestros |
| `documentos.csv` | 306 | 2-3 documentos por siniestro |
| `claims.json` | 99 | Objetos `ClaimDetail` pre-scoreados servidos por `SyntheticClaimQueries` |
| `demo_claims.json` | 99 | Snapshot del demo reconstruido vía `rescore_all` (scores genuinos del motor — ver nota abajo) |

## Distribución por tier

| Tier | Conteo | % |
|------|-------|---|
| verde (0–40) | 50 | 50.5 % |
| amarillo (41–75) | 17 | 17.2 % |
| rojo (76–100 o regla dura) | 32 | 32.3 % |

## Cobertura de señales

Las 21 señales de fraude (FS-01..FS-14, RF-01..RF-07) disparan en ≥ 3 ejemplares cada una.
Re-ejecuta `scripts/generate_dataset.py` para ver los conteos por señal.

## Estrategia de scoring

Los scores del dataset son **salida genuina del motor de reglas** (`score_claim`), nunca
fabricados. Cada siniestro se scorea con un `RuleContext` completamente poblado (todos los
flags de señal seteados explícitamente por archetype). El `score` / `tier` / `activations`
resultantes se hornean en `claims.json`; `demo_claims.json` se reconstruye con `rescore_all`
para garantizar que coincide con la lógica actual del motor. La ruta de scoring en vivo
permanece activa para siniestros nuevos sin scorear (p.ej. importados desde la UI).

## Identificadores

Todos los identificadores son hashes determinísticos (prefijo SHA-1, en mayúsculas).
Sin nombres, placas, chasis ni identificadores de póliza reales.
`etiqueta_fraude_simulada` en `siniestros.csv` es 1 para siniestros rojo, 0 en el resto
(para entrenamiento ML — sólo entrenamiento/evaluación, nunca se muestra en la UI).
