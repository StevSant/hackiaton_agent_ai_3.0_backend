# Demo Cases — Index

Import order matters for FS-13: load caso_01 before caso_06 so the pgvector similarity lookup has a prior embedding to match against.

## Folder layout — classified by ramo

Cases are grouped by **canonical ramo** under every format directory, e.g. `json/<ramo>/`, `csv/<ramo>/`, `xlsx/<ramo>/`, `sample_documents/<ramo>/<claim_id>/`. The four buckets follow the app's `normalize_ramo` taxonomy:

| Folder | Literal `ramo` values it holds |
|---|---|
| `vehiculos/` | Vehículos (caso_01–20) |
| `salud/` | Salud, Accidentes Personales (caso_21–25) |
| `vida/` | Vida (caso_26–30) |
| `hogar/` | Hogar, Incendio (caso_31–36) |

`nivel`/`score` in each JSON are the **intended** tier (engine recomputes on import via `RuleContext.from_claim`). Cases whose intended tier needs an enricher (RF-02 / RF-03 / FS-07) show a lower tier on plain import — see the per-table notes and the enrichment section below.

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
| `caso_13_verde_limpio_2.json` | Daños Parciales | — | — | VERDE | ~0 | Segunda referencia limpia. Ocurrencia 120 días desde inicio (sin FS-01). Reporte al día siguiente (sin FS-12). Ratio 5.2% (sin FS-14). Todos los docs completos. Ciudad: Ambato |
| `caso_14_borde_vigencia_2.json` | Daños Materiales | RF-05 | — | AMARILLO | RF-05 fuerza piso | Ocurrencia 1 día después del inicio de póliza (<48 h → RF-05 AMARILLO). No es robo — sin RF-01/RF-06/FS-02. Todos los docs completos. Ratio 28.7% (sin FS-14). Ciudad: Santo Domingo |
| `caso_15_robo_total_critico.json` | Pérdida Total por Robo | RF-01, RF-06 | FS-01 (+8, 8 días desde inicio), FS-14 (+5, ratio 0.971), FS-08 (+4, 2 docs faltantes) | ROJO | 76+ (RF-01 override) | Robo PTxRB (RF-01) + denuncia 6 días (RF-06) + póliza 8 días (FS-01 +8) + ratio 97.1% (FS-14 +5) + 2 docs pendientes (FS-08 +4). Alta densidad de señales auto-derivadas. Upload package disponible en `sample_documents/SIN-DEMO-015/` |
| `caso_16_late_report_verde.json` | Daños Materiales | — | FS-12 (+5, reporte 9 días), FS-08 (+4, 1 doc pendiente) | VERDE | ~9 | Sin reglas duras. Reporte tardío 9 días (FS-12 +5) + 1 doc pendiente (FS-08 +4). Ratio 40% (sin FS-14). Póliza 154 días (sin FS-01). Score ~9, bien bajo 41. Ciudad: Ibarra |
| `caso_17_borde_vigencia_3.json` | Daños Totales | RF-05 | — | AMARILLO | RF-05 fuerza piso | Ocurrencia 1 día después del inicio de póliza (<24 h → RF-05 AMARILLO). No es robo. Ratio 59.9% (sin FS-14). Todos los docs completos (sin FS-08/FS-12). Ciudad: Riobamba |
| `caso_18_robo_total_fin_poliza.json` | Pérdida Total por Robo | RF-01, RF-06 | FS-14 (+5, ratio 0.980) | ROJO | 76+ (RF-01 override) | Robo PTxRB (RF-01) + denuncia 5 días (RF-06) + ratio 98.0% (FS-14 +5). Ocurrencia 7 días ANTES del fin de vigencia — patrón de reclamo al cierre. Todos los docs entregados. Upload package disponible en `sample_documents/SIN-DEMO-018/` |
| `caso_19_verde_limpio_3.json` | Daños Parciales | — | — | VERDE | ~0 | Tercera referencia limpia. Ocurrencia 169 días desde inicio (sin FS-01). Reporte el mismo día (sin FS-12). Ratio 8.1% (sin FS-14). Todos los docs completos. Ciudad: Portoviejo |
| `caso_20_robo_parcial_amarillo.json` | Robo Parcial | RF-06 | FS-08 (+4, 1 doc pendiente) | AMARILLO | RF-06 fuerza piso | Robo de accesorios con cobertura Robo Parcial — RF-01 NO aplica (no es PTxRB). Denuncia 6 días (RF-06 AMARILLO) + 1 doc pendiente (FS-08 +4). Ratio 50% (sin FS-14). Póliza 105 días (sin FS-01). Upload package disponible en `sample_documents/SIN-DEMO-020/` |

## Non-vehicle cases — salud / vida / hogar (caso_21–36)

Authored to exercise the **ramo-agnostic** rules on non-auto claims. `Tier (auto)` is the engine result on plain import; `Intended` is the target after enrichment. Verified via `score_claim(RuleContext.from_claim(claim))`.

| File | Ramo | Cobertura | Señales auto-disparadas | Tier (auto) | Intended | Notas |
|---|---|---|---|---|---|---|
| `salud/caso_21_salud_verde_limpio.json` | Salud | Gastos Médicos Ambulatorios | — | VERDE | VERDE | Referencia limpia: consulta menor, docs completos, póliza antigua |
| `salud/caso_22_salud_docs_incompletos_late.json` | Salud | Hospitalización | FS-08, FS-12 | VERDE (9) | VERDE | Reporte 11 días tarde (FS-12 +5) + 2 docs faltantes (FS-08 +4) |
| `salud/caso_23_salud_borde_vigencia.json` | Salud | Hospitalización | FS-01, RF-05 | AMARILLO | AMARILLO | Cirugía 1 día tras el inicio de vigencia → RF-05 piso amarillo |
| `salud/caso_24_salud_monto_atipico.json` | Salud | Cirugía Mayor | FS-01, FS-14 | VERDE (13) | VERDE | Monto (26 000) supera suma (25 000) → FS-14; 8 días tras inicio → FS-01 |
| `salud/caso_25_accidentes_personales_falsificacion.json` | Accidentes Personales | Renta Diaria por Incapacidad | FS-08 | VERDE (4) | **ROJO** | Certificado con fecha anterior al accidente → **RF-02** vía enricher documental |
| `vida/caso_26_vida_verde_limpio.json` | Vida | Muerte Natural | — | VERDE | VERDE | Referencia limpia: muerte natural, póliza ~5 años, beneficiario directo |
| `vida/caso_27_vida_beneficiario_restrictivo.json` | Vida | Muerte Accidental | FS-14 | VERDE (5) | **ROJO** | Beneficiario corporativo en lista restrictiva → **RF-03** vía consulta de lista |
| `vida/caso_28_vida_borde_vigencia.json` | Vida | Muerte Accidental | FS-01, FS-14, RF-05 | AMARILLO | AMARILLO | Fallecimiento 1 día tras el inicio → RF-05 piso amarillo |
| `vida/caso_29_vida_monto_atipico_docs.json` | Vida | Muerte Natural | FS-08, FS-14 | VERDE (9) | VERDE | Reclamo 99% de la suma (FS-14) + falta partida (FS-08) |
| `vida/caso_30_vida_muerte_accidental_late_report.json` | Vida | Muerte Accidental | FS-12 | VERDE (5) | VERDE | Reporte 12 días tras el deceso (FS-12); duelo familiar |
| `hogar/caso_31_hogar_verde_limpio.json` | Hogar | Daños por Agua | — | VERDE | VERDE | Referencia limpia: daño menor, póliza antigua, docs completos |
| `hogar/caso_32_incendio_borde_vigencia.json` | Incendio | Incendio y Líneas Aliadas | FS-01, RF-05 | AMARILLO | AMARILLO | Incendio 1 día tras el inicio de vigencia → RF-05 piso amarillo |
| `hogar/caso_33_incendio_monto_atipico.json` | Incendio | Incendio y Líneas Aliadas | FS-01, FS-14 | VERDE (13) | VERDE | Pérdida = 100% de la suma (FS-14) + 8 días tras inicio (FS-01) |
| `hogar/caso_34_hogar_robo_contenidos_denuncia_tardia.json` | Hogar | Robo de Contenidos | FS-02, FS-08, FS-12, RF-06 | AMARILLO | AMARILLO | Denuncia 6 días tarde → RF-06 piso amarillo (cobertura no PTxRB → sin RF-01) |
| `hogar/caso_35_incendio_falsificacion_docs.json` | Incendio | Incendio y Líneas Aliadas | FS-14 | VERDE (5) | **ROJO** | Factura emitida después del incendio + valores tachados → **RF-02** vía enricher |
| `hogar/caso_36_hogar_proveedor_recurrente.json` | Hogar | Daños por Agua | FS-14 | VERDE (5) | VERDE/AMARILLO | Reclamo 95.3% de la suma (FS-14); proveedor recurrente → **FS-07** vía consulta de observados |

Upload packages for all 16 live under `sample_documents/<ramo>/<claim_id>/` (alert-bearing PDFs in caso_25, caso_27 and caso_35 carry the visible inconsistency text for the RF-02 / RF-03 demo).

## Rule-trigger summary per current import path (`RuleContext.from_claim`)

The current `from_claim` auto-derives: `dias_desde_inicio_poliza`, `monto_vs_suma_pct`, `es_cobertura_ptxrb`, `es_robo`, `demora_denuncia_horas`, `documentos_incompletos`. Rules that fire today without enrichment:

- RF-01 — caso_01, caso_06, caso_12, caso_15, caso_18
- RF-05 — caso_02, caso_14, caso_17
- RF-06 — caso_01, caso_06, caso_12, caso_15, caso_18, caso_20
- FS-01 — caso_02, caso_05, caso_11, caso_12, caso_15
- FS-02 — caso_01, caso_06
- FS-08 — caso_03, caso_05, caso_07, caso_09, caso_10, caso_12, caso_15, caso_16, caso_20
- FS-12 — caso_01, caso_03, caso_06, caso_16
- FS-14 — caso_01, caso_05, caso_06, caso_08, caso_11, caso_12, caso_15, caso_18

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

## Upload document packages (`sample_documents/<ramo>/`)

Cases ship a realistic PDF package ready for upload via the frontend file-upload flow,
under `sample_documents/<ramo>/<claim_id>/`. Each PDF filename contains the keyword required
by `sync_claim_document._FILENAME_TIPO_HINTS` so the document tipo is inferred automatically
on upload. The vehiculos packages (under `sample_documents/vehiculos/`) are:

| Claim ID | Case | PDFs included | Notable feature |
|---|---|---|---|
| SIN-DEMO-007 | caso_07_falsificacion_docs | cedula, matricula, acta, peritaje, proforma, caratula (6 PDFs) | `proforma_taller.pdf` has emission date 18/04 — 2 days before siniestro 20/04 (RF-02 demo) |
| SIN-DEMO-009 | caso_09_dinamica_imposible | cedula, matricula, acta, peritaje, proforma, caratula, denuncia (7 PDFs) | `peritaje_tecnico.pdf` flags lateral/rear damage vs. frontal collision (RF-04 demo) |
| SIN-DEMO-012 | caso_12_robo_multi_senal | cedula, matricula, denuncia, acta, peritaje, caratula (6 PDFs) | `denuncia_fiscal.pdf` shows 10-day delay; `caratula_poliza.pdf` shows 5-day-old policy (RF-01+RF-06 demo) |
| SIN-DEMO-015 | caso_15_robo_total_critico | cedula, matricula, denuncia, acta, peritaje, caratula (6 PDFs) | `denuncia_fiscal.pdf` shows 6-day delay; `caratula_poliza.pdf` shows 8-day-old policy; RF-01+RF-06+FS-01+FS-14+FS-08 demo |
| SIN-DEMO-018 | caso_18_robo_total_fin_poliza | cedula, matricula, denuncia, acta, peritaje, caratula (6 PDFs) | `denuncia_fiscal.pdf` shows 5-day delay; `caratula_poliza.pdf` shows policy expiring 7 days after event; RF-01+RF-06+FS-14 demo |
| SIN-DEMO-020 | caso_20_robo_parcial_amarillo | cedula, matricula, denuncia, acta, peritaje, caratula (6 PDFs) | Robo Parcial (NOT PTxRB — RF-01 absent); `denuncia_fiscal.pdf` shows 6-day delay; RF-06+FS-08 AMARILLO demo |

Generate packages: `uv run python scripts/generate_demo_case_docs.py`
