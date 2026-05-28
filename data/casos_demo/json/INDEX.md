# Demo Cases — Index

Import order matters for FS-13: load caso_01 before caso_06 so the pgvector similarity lookup has a prior embedding to match against.

| File | Cobertura | Hard rules expected | Signal rules expected | Expected tier (post-enrichment) | Score estimate (post-enrichment) | Notes |
|---|---|---|---|---|---|---|
| `caso_01_robo_total_PTxRB.json` | Pérdida Total por Robo | RF-01, RF-06 | FS-02 (+8), FS-12 (+3), FS-14 (+5) | ROJO | 76+ (RF-01 override) | Baseline reference; import first so FS-13 has a prior to compare against |
| `caso_02_borde_vigencia.json` | Daños Materiales | RF-05 | FS-01 (+8) | AMARILLO | 8 additive but RF-05 forces floor | RF-05 fires because ocurrencia is 1 day after inicio_poliza (<48 h). No theft → no FS-02/RF-06. All docs complete, no FS-08/FS-12 |
| `caso_03_docs_incompletos_late_report.json` | Daños | — | FS-08 (+4), FS-12 (+5) | VERDE | ~9 | No hard rules. 10-day delay triggers FS-12 high (+5); 2 missing docs trigger FS-08 (+4). Score stays well below 41 |
| `caso_04_verde_limpio.json` | Daños Parciales | — | — | VERDE | ~0 | Fecha_ocurrencia 140 days after inicio_poliza — no FS-01. 2-day report delay — no FS-12. Ratio 0.043 — no FS-14. All docs complete. Intended clean reference case |
| `caso_05_amarillo_borderline.json` | Daños Totales | — | FS-01 (+8), FS-08 (+4), FS-12 (+5), FS-14 (+5), FS-07 (+10 needs enrichment), FS-09 (+6 needs enrichment), FS-13 (+4 needs enrichment) | AMARILLO | ~42 after full enrichment; ~22 with current import only | FS-07 needs restrictive-list lookup (proveedor "Taller Mecánico Auto-Élite"). FS-09 needs NLP flag for madrugada + no-witness narrative. FS-13 needs pgvector similarity pass |
| `caso_06_robo_narrativa_similar_FS13.json` | Pérdida Total por Robo | RF-01, RF-06 | FS-02 (+8), FS-12 (+3), FS-14 (+5), FS-13 (+8 needs enrichment) | ROJO | 76+ (RF-01 override) + FS-13 bonus | FS-13 fires when imported after caso_01 — narrative is a deliberate paraphrase (~85-95% cosine similarity). Must NOT trigger RF-07 (clone ≥0.98 threshold). Import orden: caso_01 first |

## Rule-trigger summary per current import path (`RuleContext.from_claim`)

The current `from_claim` auto-derives: `dias_desde_inicio_poliza`, `monto_vs_suma_pct`, `es_cobertura_ptxrb`, `es_robo`, `demora_denuncia_horas`, `documentos_incompletos`. Rules that fire today without enrichment:

- RF-01 — caso_01, caso_06
- RF-05 — caso_02
- RF-06 — caso_01, caso_06
- FS-01 — caso_02, caso_05
- FS-02 — caso_01, caso_06
- FS-08 — caso_03, caso_05
- FS-12 — caso_01, caso_03, caso_06
- FS-14 — caso_01, caso_05, caso_06

## Rules that require Slice 2 enrichment

| Rule | Required enrichment | Affected cases |
|---|---|---|
| RF-02 | `falsificacion_evidente=True` set by document-review enricher | None in current set (no falsification case) |
| RF-03 | `proveedor_en_lista_restrictiva=True` set by restrictive-list lookup | None in current set (caso_05 uses FS-07, not RF-03) |
| FS-07 | `proveedor_en_lista_restrictiva=True` OR `proveedor_casos_observados > 2` | caso_05 (via restrictive-list lookup for "Taller Mecánico Auto-Élite") |
| FS-09 | `narrativa_ilógica=True` or `evento_medianoche=True` set by NLP layer | caso_05 (madrugada, sin testigos) |
| FS-13 | `narrativa_similar_score` set by pgvector similarity pass | caso_06 vs caso_01 |
