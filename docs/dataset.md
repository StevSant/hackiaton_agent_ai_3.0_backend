# Synthetic Dataset — Fraudia Claims

## Origin

Fully synthetic; no real PII (challenge §2.10).
Generated deterministically from `app/use_cases/generate_dataset/_archetypes.py`
via `scripts/generate_dataset.py` (or `app.use_cases.generate_dataset.generate_and_save`).

## Files (`data/synthetic/`)

| File | Rows | Description |
|------|------|-------------|
| `claims.json` | 99 | Pre-scored `ClaimDetail` objects served by `SyntheticClaimQueries` |
| `demo_claims.json` | 99 | Demo snapshot rebuilt via `rescore_all` (genuine engine scores — see note below) |
| `siniestros.csv` | 99 | §2.8 main table |
| `polizas.csv` | 99 | One policy per claim (approximation) |
| `asegurados.csv` | 99 | One insured per claim |
| `beneficiarios_proveedores.csv` | 54 | Unique providers across claims |
| `documentos.csv` | 306 | 2-3 documents per claim |

## Tier Distribution

| Tier | Count | % |
|------|-------|---|
| verde (0–40) | 50 | 50.5 % |
| amarillo (41–75) | 17 | 17.2 % |
| rojo (76–100 or hard rule) | 32 | 32.3 % |

## Signal Coverage

All 21 fraud signals (FS-01..FS-14, RF-01..RF-07) fire in ≥ 3 exemplars each.
Re-run `scripts/generate_dataset.py` to see the per-signal counts.

## Pre-scoring strategy

Each claim is scored at generation time with a fully-populated `RuleContext`
(all signal flags set explicitly per archetype).  The resulting `score`/`nivel`/
`alertas` are baked into `claims.json`.  `get_claim_detail` skips re-scoring
when `alertas` is non-empty (double-scoring guard) to preserve these rich scores.
The live-scoring path remains active for future un-scored DB claims.

## Identifiers

All identifiers are deterministic hashes (SHA-1 prefix, uppercased).
No real names, plates, chassis numbers, or policy identifiers.
`etiqueta_fraude_simulada` in `siniestros.csv` is 1 for rojo claims, 0 otherwise
(for ML training — training/eval only, never shown in the UI).
