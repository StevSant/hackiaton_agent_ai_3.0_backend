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
| `caso_07_falsificacion_docs.json` | Daños Materiales | RF-02 (needs enrichment) | FS-08 (+4, 2 docs missing) | AMARILLO | ~4 auto; ~4+ after enrichment if RF-02 sets amarillo floor | Proforma de taller con fecha de emisión 2 días ANTES del siniestro — inconsistencia documental visible. RF-02 (`falsificacion_evidente=True`) requiere el document-review enricher; sin él el caso llega solo por FS-08. Caso demo para revisar "requiere revisión" en la bandeja. Upload package disponible en `sample_documents/SIN-DEMO-007/` |
| `caso_08_proveedor_recurrente.json` | Daños Materiales | — | FS-14 (+5, ratio 0.96), FS-07 (+10 needs enrichment), FS-08 (+4, 1 doc missing) | AMARILLO | ~9 auto; ~19 after enrichment | Proveedor "Taller Mecánico Auto-Élite" (mismo que caso_05) — aparece en múltiples reclamos. FS-07 necesita `proveedor_casos_observados > 2` (restrictive-list/observed enricher). FS-14 auto-fires por ratio 0.96 |
| `caso_09_dinamica_imposible.json` | Daños Totales | RF-04 (needs enrichment) | FS-08 (+4, 2 docs missing) | AMARILLO | ~4 auto; RF-04 eleva a AMARILLO mínimo post-enrichment | Colisión frontal declarada pero daños solo en lateral y trasero; registro de cámara contradice ubicación. RF-04 (`narrativa_ilógica=True`) requiere NLP enricher. Caso demo de dinámica físicamente imposible. Upload package disponible en `sample_documents/SIN-DEMO-009/` |
| `caso_10_alta_frecuencia.json` | Daños Materiales | — | FS-08 (+4, 2 docs missing), FS-03/05 (needs enrichment, +8 if historial≥3 en 18m) | AMARILLO | ~4 auto; ~12 after enrichment | Tercer reclamo en 14 meses — narrativa lo menciona explícitamente. FS-03 y FS-05 requieren `historial_siniestros_asegurado` y `historial_conductor` del enricher. Sin enriquecimiento solo dispara FS-08 |
| `caso_11_monto_atipico.json` | Daños Totales | — | FS-14 (+5, ratio 1.05 > 1.0), FS-01 (+8, 15 días desde inicio) | AMARILLO | ~13 auto (FS-14 + FS-01 directo) | monto_reclamado (31 500) SUPERA suma_asegurada (30 000) → ratio 1.05 → FS-14 auto-fires. Póliza iniciada 15 días antes → FS-01 (+8). Todos los docs completos — sin FS-08. Caso limpio de múltiples señales auto-derivadas |
| `caso_12_robo_multi_senal.json` | Pérdida Total por Robo | RF-01, RF-06 | FS-01 (+8, 5 días desde inicio), FS-14 (+5, ratio 0.977), FS-08 (+4, 2 docs faltantes) | ROJO | 76+ (RF-01 override) | Robo PTxRB (RF-01) + demora denuncia 10 días (RF-06, >4 días) + póliza 5 días antes (FS-01 +8) + ratio 0.977 (FS-14 +5) + 2 docs pendientes (FS-08 +4). Máxima densidad de señales auto-derivadas. Upload package disponible en `sample_documents/SIN-DEMO-012/` |

## Rule-trigger summary per current import path (`RuleContext.from_claim`)

The current `from_claim` auto-derives: `dias_desde_inicio_poliza`, `monto_vs_suma_pct`, `es_cobertura_ptxrb`, `es_robo`, `demora_denuncia_horas`, `documentos_incompletos`. Rules that fire today without enrichment:

- RF-01 — caso_01, caso_06, caso_12
- RF-05 — caso_02
- RF-06 — caso_01, caso_06, caso_12
- FS-01 — caso_02, caso_05, caso_11, caso_12
- FS-02 — caso_01, caso_06
- FS-08 — caso_03, caso_05, caso_07, caso_09, caso_10, caso_12
- FS-12 — caso_01, caso_03, caso_06
- FS-14 — caso_01, caso_05, caso_06, caso_08, caso_11, caso_12

## Rules that require Slice 2 enrichment

| Rule | Required enrichment | Affected cases |
|---|---|---|
| RF-02 | `falsificacion_evidente=True` set by document-review enricher | caso_07 (proforma con fecha anterior al siniestro) |
| RF-03 | `proveedor_en_lista_restrictiva=True` set by restrictive-list lookup | None in current set (caso_05/08 use FS-07, not RF-03) |
| RF-04 | `narrativa_ilógica=True` set by NLP layer (physically impossible dynamics) | caso_09 (daños incompatibles con colisión declarada) |
| FS-03 | `historial_siniestros_asegurado ≥ 2` from claims history enricher | caso_10 (tercer siniestro en 14 meses) |
| FS-05 | `historial_conductor ≥ 2` from claims history enricher | caso_10 |
| FS-07 | `proveedor_en_lista_restrictiva=True` OR `proveedor_casos_observados > 2` | caso_05, caso_08 (via restrictive-list lookup for "Taller Mecánico Auto-Élite") |
| FS-09 | `narrativa_ilógica=True` or `evento_medianoche=True` set by NLP layer | caso_05 (madrugada, sin testigos) |
| FS-13 | `narrativa_similar_score` set by pgvector similarity pass | caso_06 vs caso_01 |

## Upload document packages (`sample_documents/`)

Three cases have a realistic PDF package ready for upload via the frontend file-upload flow.
Each PDF filename contains the keyword required by `sync_claim_document._FILENAME_TIPO_HINTS`
so the document tipo is inferred automatically on upload.

| Claim ID | Case | PDFs included | Notable feature |
|---|---|---|---|
| SIN-DEMO-007 | caso_07_falsificacion_docs | cedula, matricula, acta, peritaje, proforma, caratula (6 PDFs) | `proforma_taller.pdf` has emission date 18/04 — 2 days before siniestro 20/04 (RF-02 demo) |
| SIN-DEMO-009 | caso_09_dinamica_imposible | cedula, matricula, acta, peritaje, proforma, caratula, denuncia (7 PDFs) | `peritaje_tecnico.pdf` flags lateral/rear damage vs. frontal collision (RF-04 demo) |
| SIN-DEMO-012 | caso_12_robo_multi_senal | cedula, matricula, denuncia, acta, peritaje, caratula (6 PDFs) | `denuncia_fiscal.pdf` shows 10-day delay; `caratula_poliza.pdf` shows 5-day-old policy (RF-01+RF-06 demo) |

Generate packages: `uv run python scripts/generate_demo_case_docs.py`
