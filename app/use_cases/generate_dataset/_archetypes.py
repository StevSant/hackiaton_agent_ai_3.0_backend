"""Archetype catalogue for the synthetic generator.

Each ``ClaimArchetype`` is a *template* that carries the signal flags needed to
make specific rules fire.  The actual ``ClaimDetail`` / ``RuleContext`` objects
are assembled by ``_claim_builder.build_claim``.

Design notes:
- Every FS/RF code must appear in ≥ 3 archetypes across the full list.
- Archetypes are deterministically seeded — no random state here.
- Tier targets: ≥ 15 verde, ≥ 20 amarillo, ≥ 15 rojo out of ~70 total.
- Single-signal archetypes for low-value codes score <= 8 pts (stays verde).
  Tier-spanning archetypes stack signals to reach 41+ pts (amarillo) or add
  hard rules (RF) for rojo.
- Field names shadow ``RuleContext`` fields so the builder can set them directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClaimArchetype:
    """Template that drives both ClaimDetail fields and RuleContext flags."""

    label: str                    # human label for coverage report
    target_signals: list[str]     # rule codes expected to fire

    # ── ClaimDetail fields ────────────────────────────────────────────────────
    ramo: str = "Vehículos"
    cobertura: str = "Daños"
    ciudad: str = "Guayaquil"
    estado: str = "Reserva"
    # relative monto vs suma: monto = sum_asegurada * monto_ratio
    monto_ratio: float = 0.30
    suma_asegurada: float = 20_000.0
    fecha_ocurrencia_offset: int = 90   # days before "today" (2026-05-26)
    reporte_delay_days: int = 1

    # ── RuleContext overrides (None = keep default = non-firing) ──────────────
    dias_desde_inicio_poliza: int | None = None
    historial_siniestros_asegurado: int | None = None
    frecuencia_vehiculo: int | None = None
    frecuencia_conductor: int | None = None
    eventos_rc_previos: int | None = None
    proveedor_en_lista_restrictiva: bool = False
    beneficiario_en_lista_restrictiva: bool = False
    proveedor_casos_observados: int = 0
    documentos_incompletos: bool = False
    inconsistencia_documental: bool = False
    falsificacion_evidente: bool = False
    narrativa_similar_score: float = 0.0
    narrativa_clonada: bool = False
    dinamica_imposible: bool = False
    sin_rastro_tercero: bool = False
    evento_medianoche: bool = False
    monto_vs_reparacion_avg_pct: float = 0.0
    es_robo: bool = False
    es_cobertura_ptxrb: bool = False
    demora_denuncia_horas: float = 0.0
    cobertura_rc: bool = False
    narrativa_ilógica: bool = False

    # ── optional doc list overrides ───────────────────────────────────────────
    docs_faltantes: list[str] = field(default_factory=list)
    proveedor: str | None = None

    # ── optional narrative text (None = auto) ────────────────────────────────
    descripcion: str | None = None


# ---------------------------------------------------------------------------
# ARCHETYPES
# Tier targets: ~18 verde / ~25 amarillo / ~20 rojo
# Coverage: every FS/RF code ≥ 3 times
# ---------------------------------------------------------------------------

ARCHETYPES: list[ClaimArchetype] = [
    # ════════════════════════════════════════════════════════════════════
    # VERDE (score 0-40, no hard rules) — 18 archetypes
    # ════════════════════════════════════════════════════════════════════
    ClaimArchetype(
        label="verde-clean-01",
        target_signals=[],
        ramo="Vehículos", cobertura="Responsabilidad Civil",
        ciudad="Guayaquil", estado="Cierre Sin Consecuencia",
        monto_ratio=0.05, suma_asegurada=18_000.0,
        cobertura_rc=True,
        descripcion="Colisión menor en parqueo. Daño leve en guardafango.",
    ),
    ClaimArchetype(
        label="verde-clean-02",
        target_signals=[],
        ramo="Accidentes Personales", cobertura="Cobertura Básica",
        ciudad="Quito", estado="Pago Total",
        monto_ratio=0.10, suma_asegurada=10_000.0,
        descripcion="Accidente de tránsito menor, sin lesionados graves.",
    ),
    ClaimArchetype(
        label="verde-clean-03",
        target_signals=[],
        ramo="Incendio", cobertura="Todo Riesgo",
        ciudad="Cuenca", estado="Liquidado",
        monto_ratio=0.08, suma_asegurada=50_000.0,
        descripcion="Cortocircuito menor en cocina. Daños menores reparados.",
    ),
    ClaimArchetype(
        label="verde-clean-04",
        target_signals=[],
        ramo="Vehículos", cobertura="Daños Parciales",
        ciudad="Machala", estado="Pago Parcial",
        monto_ratio=0.15, suma_asegurada=12_000.0,
        descripcion="Impacto con objeto fijo en vía urbana.",
    ),
    ClaimArchetype(
        label="verde-clean-05",
        target_signals=[],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Loja", estado="Liquidado",
        monto_ratio=0.12, suma_asegurada=14_000.0,
        descripcion="Raspón leve con poste; sin lesionados.",
    ),
    ClaimArchetype(
        label="verde-clean-06",
        target_signals=[],
        ramo="Accidentes Personales", cobertura="Cobertura Básica",
        ciudad="Ambato", estado="Pago Total",
        monto_ratio=0.09, suma_asegurada=8_000.0,
        descripcion="Caída en escaleras; lesión leve; documentación completa.",
    ),
    ClaimArchetype(
        label="verde-fs01-low",
        target_signals=["FS-01"],
        ramo="Vehículos", cobertura="Daños Parciales",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.20, suma_asegurada=15_000.0,
        dias_desde_inicio_poliza=20,   # tier2: 4 pts, stays verde
        reporte_delay_days=1,
        descripcion="Colisión a 20 días del inicio de póliza.",
    ),
    ClaimArchetype(
        label="verde-fs02-low",
        target_signals=["FS-02"],
        ramo="Vehículos", cobertura="Robo Parcial",
        ciudad="Manta", estado="Reserva",
        monto_ratio=0.20, suma_asegurada=14_000.0,
        es_robo=True, demora_denuncia_horas=36.0,  # mid: 4 pts, stays verde
        reporte_delay_days=2,
        descripcion="Robo de radio; denuncia al día siguiente.",
    ),
    ClaimArchetype(
        label="verde-fs03-low",
        target_signals=["FS-03"],
        ramo="Accidentes Personales", cobertura="Cobertura Amplia",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.20, suma_asegurada=8_000.0,
        historial_siniestros_asegurado=2,  # mid: 4 pts, stays verde
        reporte_delay_days=1,
        descripcion="Segundo siniestro del asegurado este año.",
    ),
    ClaimArchetype(
        label="verde-fs04-low",
        target_signals=["FS-04"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.20, suma_asegurada=15_000.0,
        frecuencia_vehiculo=2,  # mid: 3 pts, stays verde
        reporte_delay_days=1,
        descripcion="Segunda colisión para el mismo vehículo.",
    ),
    ClaimArchetype(
        label="verde-fs05-low",
        target_signals=["FS-05"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.22, suma_asegurada=14_000.0,
        frecuencia_conductor=2,  # mid: 4 pts, stays verde
        reporte_delay_days=1,
        descripcion="Conductor con dos siniestros previos este ciclo.",
    ),
    ClaimArchetype(
        label="verde-fs06-low",
        target_signals=["FS-06"],
        ramo="Vehículos", cobertura="Responsabilidad Civil",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.15, suma_asegurada=10_000.0,
        eventos_rc_previos=1, cobertura_rc=True,  # mid: 3 pts, stays verde
        reporte_delay_days=1,
        descripcion="Patrón RC observado por segunda vez en el asegurado.",
    ),
    ClaimArchetype(
        label="verde-fs12-low",
        target_signals=["FS-12"],
        ramo="Accidentes Personales", cobertura="Cobertura Básica",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.18, suma_asegurada=9_000.0,
        reporte_delay_days=5,  # mid: 3 pts, stays verde
        descripcion="Reporte presentado cinco días después del accidente.",
    ),
    ClaimArchetype(
        label="verde-fs08-low",
        target_signals=["FS-08"],
        ramo="Accidentes Personales", cobertura="Cobertura Básica",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.22, suma_asegurada=7_000.0,
        documentos_incompletos=True,
        docs_faltantes=["Historial médico"],  # 4 pts, stays verde
        reporte_delay_days=1,
        descripcion="Accidente personal; historial clínico no aportado.",
    ),
    ClaimArchetype(
        label="verde-fs10-low",
        target_signals=["FS-10"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Portoviejo", estado="Reserva",
        monto_ratio=0.35, suma_asegurada=16_000.0,
        sin_rastro_tercero=True,  # 6 pts, stays verde
        reporte_delay_days=2,
        descripcion="Daño moderado sin rastro de terceros; zona aislada.",
    ),
    ClaimArchetype(
        label="verde-fs14-low",
        target_signals=["FS-14"],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.97,  # 5 pts, stays verde
        suma_asegurada=10_000.0,
        reporte_delay_days=1,
        descripcion="Reclamación por monto casi igual a la suma asegurada.",
    ),
    ClaimArchetype(
        label="verde-fs09-low",
        target_signals=["FS-09"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.25, suma_asegurada=16_000.0,
        evento_medianoche=True,  # 3 pts, stays verde
        reporte_delay_days=1,
        descripcion="Incidente menor ocurrido a medianoche.",
    ),
    ClaimArchetype(
        label="verde-fs13-low",
        target_signals=["FS-13"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.30, suma_asegurada=16_000.0,
        narrativa_similar_score=0.72,  # mid: 4 pts, stays verde
        reporte_delay_days=2,
        descripcion="Descripción con similitud media a casos anteriores.",
    ),

    # ════════════════════════════════════════════════════════════════════
    # AMARILLO — 25 archetypes (score 41-75 OR RF-05/RF-06/RF-07 fires)
    # ════════════════════════════════════════════════════════════════════

    # RF-05: extreme claim near policy edge (< 2 days) → amarillo floor
    ClaimArchetype(
        label="amarillo-rf05-01",
        target_signals=["FS-01", "RF-05"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Ambato", estado="Reserva",
        monto_ratio=0.60, suma_asegurada=22_000.0,
        dias_desde_inicio_poliza=1,  # RF-05 fires
        reporte_delay_days=1,
        descripcion="Vehículo siniestrado el primer día de vigencia de la póliza.",
    ),
    ClaimArchetype(
        label="amarillo-rf05-02",
        target_signals=["FS-01", "FS-08", "RF-05"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.55, suma_asegurada=20_000.0,
        dias_desde_inicio_poliza=0,  # same day → RF-05
        documentos_incompletos=True,
        docs_faltantes=["Denuncia policial"],
        reporte_delay_days=1,
        descripcion="Siniestro el mismo día de inicio de póliza; documentación incompleta.",
    ),
    ClaimArchetype(
        label="amarillo-rf05-03",
        target_signals=["FS-01", "FS-03", "RF-05"],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.70, suma_asegurada=28_000.0,
        dias_desde_inicio_poliza=1,  # RF-05
        historial_siniestros_asegurado=3,  # FS-03 high
        reporte_delay_days=1,
        descripcion="Primer día de póliza; asegurado con historial elevado.",
    ),

    # RF-06: atypical theft delay > 4 days → amarillo floor
    ClaimArchetype(
        label="amarillo-rf06-01",
        target_signals=["FS-02", "RF-06"],
        ramo="Vehículos", cobertura="Robo Parcial",
        ciudad="Esmeraldas", estado="Reserva",
        monto_ratio=0.50, suma_asegurada=18_000.0,
        es_robo=True, demora_denuncia_horas=110.0,  # RF-06 fires
        reporte_delay_days=5,
        descripcion="Robo de accesorios; denuncia policial tardía (110 h).",
    ),
    ClaimArchetype(
        label="amarillo-rf06-02",
        target_signals=["FS-02", "FS-08", "RF-06"],
        ramo="Vehículos", cobertura="Robo Total",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.90, suma_asegurada=25_000.0,
        es_robo=True, demora_denuncia_horas=120.0,  # RF-06
        documentos_incompletos=True,
        docs_faltantes=["Matrícula"],
        reporte_delay_days=5,
        descripcion="Vehículo robado; denuncia 5 días después; documentación incompleta.",
    ),
    ClaimArchetype(
        label="amarillo-rf06-03",
        target_signals=["FS-02", "FS-12", "RF-06"],
        ramo="Vehículos", cobertura="Robo Parcial",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.45, suma_asegurada=16_000.0,
        es_robo=True, demora_denuncia_horas=100.0,  # RF-06
        reporte_delay_days=10,  # FS-12 high
        descripcion="Robo con denuncia tardía y reporte tardío al asegurador.",
    ),

    # RF-07: cloned narrative → amarillo floor
    ClaimArchetype(
        label="amarillo-rf07-01",
        target_signals=["FS-13", "RF-07"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.50, suma_asegurada=20_000.0,
        narrativa_similar_score=0.99, narrativa_clonada=True,  # RF-07
        reporte_delay_days=2,
        descripcion="Colisión en autopista; narrativa idéntica a caso previo SIN-F030.",
    ),
    ClaimArchetype(
        label="amarillo-rf07-02",
        target_signals=["FS-13", "FS-08", "RF-07"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.60, suma_asegurada=22_000.0,
        narrativa_similar_score=0.98, narrativa_clonada=True,  # RF-07
        documentos_incompletos=True,
        docs_faltantes=["Denuncia"],
        reporte_delay_days=3,
        descripcion="Narrativa clonada detectada; documentación incompleta.",
    ),
    ClaimArchetype(
        label="amarillo-rf07-03",
        target_signals=["FS-13", "FS-09", "RF-07"],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.55, suma_asegurada=19_000.0,
        narrativa_similar_score=0.99, narrativa_clonada=True,  # RF-07
        narrativa_ilógica=True,  # FS-09
        reporte_delay_days=2,
        descripcion="Narrativa idéntica a caso SIN-F031 con dinámica inconsistente.",
    ),

    # Multi-signal stacked → score 41-75
    ClaimArchetype(
        label="amarillo-stacked-01",
        target_signals=["FS-01", "FS-03", "FS-12"],
        ramo="Vehículos", cobertura="Daños Parciales",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.35, suma_asegurada=18_000.0,
        dias_desde_inicio_poliza=7,   # FS-01: 8 pts
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        reporte_delay_days=10,             # FS-12: 5 pts → 21 pts... need more
        descripcion="Siniestro a 7 días del inicio; historial elevado; reporte tardío.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-02",
        target_signals=["FS-03", "FS-05", "FS-07", "FS-08"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.45, suma_asegurada=20_000.0,
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        frecuencia_conductor=3,            # FS-05: 8 pts
        proveedor="Taller Pacífico Sur",
        proveedor_casos_observados=4,      # FS-07: 5 pts
        documentos_incompletos=True,
        docs_faltantes=["Proforma"],       # FS-08: 4 pts → 25 pts
        reporte_delay_days=2,
        descripcion="Frecuencia alta asegurado+conductor; proveedor observado; docs incompletos.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-03",
        target_signals=["FS-01", "FS-05", "FS-09", "FS-12"],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.50, suma_asegurada=22_000.0,
        dias_desde_inicio_poliza=7,   # FS-01: 8 pts
        frecuencia_conductor=3,       # FS-05: 8 pts
        narrativa_ilógica=True,       # FS-09: 6 pts
        reporte_delay_days=8,         # FS-12: 5 pts → 27 pts still verde...
        descripcion="Múltiples señales: inicio póliza, frecuencia conductor, dinámica anómala.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-04",
        target_signals=["FS-03", "FS-04", "FS-05", "FS-06", "FS-08"],
        ramo="Vehículos", cobertura="Responsabilidad Civil",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.25, suma_asegurada=12_000.0,
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        frecuencia_vehiculo=3,             # FS-04: 6 pts
        frecuencia_conductor=3,            # FS-05: 8 pts
        eventos_rc_previos=3,              # FS-06: 6 pts
        documentos_incompletos=True,
        docs_faltantes=["Cédula"],         # FS-08: 4 pts → 32 pts
        cobertura_rc=True,
        reporte_delay_days=2,
        descripcion="Alta frecuencia vehículo+conductor+asegurado+RC; docs incompletos.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-05",
        target_signals=["FS-01", "FS-07", "FS-11", "FS-12"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.55, suma_asegurada=20_000.0,
        dias_desde_inicio_poliza=7,        # FS-01: 8 pts
        proveedor="Carrocerías Manabí",
        proveedor_casos_observados=4,      # FS-07: 5 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        reporte_delay_days=5,              # FS-12: 3 pts → 21 pts
        descripcion="Siniestro temprano; proveedor observado; inconsistencia documental.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-06",
        target_signals=["FS-03", "FS-07", "FS-09", "FS-10", "FS-14"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=24_000.0,
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        proveedor="Servicar Andinos",
        proveedor_casos_observados=3,      # FS-07: 5 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts → 30 pts
        reporte_delay_days=2,
        descripcion="Asegurado frecuente; proveedor observado; dinámica anómala; daño sin rastro.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-07",
        target_signals=["FS-01", "FS-03", "FS-04", "FS-08", "FS-12"],
        ramo="Vehículos", cobertura="Pérdida Parcial",
        ciudad="Ambato", estado="Reserva",
        monto_ratio=0.40, suma_asegurada=18_000.0,
        dias_desde_inicio_poliza=7,        # FS-01: 8 pts
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        frecuencia_vehiculo=3,             # FS-04: 6 pts
        documentos_incompletos=True,
        docs_faltantes=["Proforma"],       # FS-08: 4 pts
        reporte_delay_days=8,              # FS-12: 5 pts → 31 pts
        descripcion="Inicio de póliza + frecuencia alta vehículo+asegurado + docs tardíos.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-08",
        target_signals=["FS-05", "FS-07", "FS-09", "FS-10", "FS-11"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.70, suma_asegurada=26_000.0,
        frecuencia_conductor=3,            # FS-05: 8 pts
        proveedor="Reparaciones El Valle",
        proveedor_casos_observados=4,      # FS-07: 5 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts → 30 pts
        reporte_delay_days=2,
        descripcion="Conductor frecuente; proveedor observado; dinámica incoherente; sin rastro.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-09",
        target_signals=["FS-03", "FS-06", "FS-07", "FS-12", "FS-14"],
        ramo="Vehículos", cobertura="Responsabilidad Civil",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=14_000.0,
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        eventos_rc_previos=3,              # FS-06: 6 pts
        proveedor="Multiservicios Quevedo",
        proveedor_casos_observados=3,      # FS-07: 5 pts
        reporte_delay_days=8,              # FS-12: 5 pts → 29 pts
        cobertura_rc=True,
        descripcion="RC recurrente; asegurado frecuente; proveedor observado; monto alto.",
    ),
    ClaimArchetype(
        label="amarillo-stacked-10",
        target_signals=["FS-02", "FS-03", "FS-07", "FS-11", "FS-13"],
        ramo="Vehículos", cobertura="Robo Parcial",
        ciudad="Manta", estado="Reserva",
        monto_ratio=0.60, suma_asegurada=20_000.0,
        es_robo=True, demora_denuncia_horas=80.0,  # FS-02: 8 pts
        historial_siniestros_asegurado=3,           # FS-03: 8 pts
        proveedor="Tecnomotor Loja",
        proveedor_casos_observados=4,               # FS-07: 5 pts
        inconsistencia_documental=True,             # FS-11: 5 pts
        narrativa_similar_score=0.75,               # FS-13: 4 pts → 30 pts
        reporte_delay_days=4,
        descripcion="Robo con demora; asegurado frecuente; docs inconsistentes; narrativa similar.",
    ),
    ClaimArchetype(
        label="amarillo-heavy-01",
        target_signals=["FS-01", "FS-03", "FS-05", "FS-07", "FS-08", "FS-12"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.50, suma_asegurada=22_000.0,
        dias_desde_inicio_poliza=7,        # FS-01: 8 pts
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        frecuencia_conductor=3,            # FS-05: 8 pts
        proveedor="Taller Costa Brava",
        proveedor_casos_observados=3,      # FS-07: 5 pts
        documentos_incompletos=True,
        docs_faltantes=["Proforma", "Cédula"],  # FS-08: 4 pts
        reporte_delay_days=8,              # FS-12: 5 pts → 38 pts (still verde!)
        descripcion="Seis señales: póliza, asegurado, conductor, proveedor, docs, reporte.",
    ),
    ClaimArchetype(
        label="amarillo-heavy-02",
        target_signals=["FS-03", "FS-04", "FS-05", "FS-09", "FS-10", "FS-11", "FS-14"],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=30_000.0,
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        frecuencia_vehiculo=3,             # FS-04: 6 pts
        frecuencia_conductor=3,            # FS-05: 8 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts → 44 pts → amarillo!
        reporte_delay_days=2,
        descripcion="Siete señales: frecuencias alta+alta+alta, dinámica, daño, doc, monto.",
    ),
    ClaimArchetype(
        label="amarillo-heavy-03",
        target_signals=["FS-01", "FS-03", "FS-07", "FS-09", "FS-10", "FS-11", "FS-12"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.65, suma_asegurada=25_000.0,
        dias_desde_inicio_poliza=7,        # FS-01: 8 pts
        historial_siniestros_asegurado=4,  # FS-03: 8 pts
        proveedor="Auto Express La Aurora",
        proveedor_casos_observados=4,      # FS-07: 5 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        reporte_delay_days=9,              # FS-12: 5 pts → 43 pts → amarillo!
        descripcion="Inicio de póliza; asegurado frecuente; proveedor observado; 7 señales.",
    ),
    ClaimArchetype(
        label="amarillo-heavy-04",
        target_signals=["FS-02", "FS-05", "FS-06", "FS-07", "FS-09", "FS-10", "FS-13"],
        ramo="Vehículos", cobertura="Robo Parcial",
        ciudad="Esmeraldas", estado="Reserva",
        monto_ratio=0.55, suma_asegurada=18_000.0,
        es_robo=True, demora_denuncia_horas=60.0,   # FS-02: 8 pts
        frecuencia_conductor=4,                     # FS-05: 8 pts
        eventos_rc_previos=3,                       # FS-06: 6 pts
        proveedor="Mecánica Universal Daule",
        proveedor_casos_observados=3,               # FS-07: 5 pts
        narrativa_ilógica=True,                     # FS-09: 6 pts
        sin_rastro_tercero=True,                    # FS-10: 6 pts
        narrativa_similar_score=0.78,               # FS-13: 4 pts → 43 pts → amarillo!
        reporte_delay_days=3,
        descripcion="Robo con demora; conductor+RC frecuentes; proveedor observado; similar.",
    ),
    ClaimArchetype(
        label="amarillo-heavy-05",
        target_signals=["FS-04", "FS-06", "FS-07", "FS-08", "FS-11", "FS-12", "FS-14"],
        ramo="Vehículos", cobertura="Responsabilidad Civil",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=14_000.0,
        frecuencia_vehiculo=3,             # FS-04: 6 pts
        eventos_rc_previos=4,              # FS-06: 6 pts
        proveedor="Talleres Salinas",
        proveedor_casos_observados=4,      # FS-07: 5 pts
        documentos_incompletos=True,
        docs_faltantes=["Licencia"],       # FS-08: 4 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        reporte_delay_days=10,             # FS-12: 5 pts → 36 pts still verde
        cobertura_rc=True,
        descripcion="RC frecuente; vehículo repetido; proveedor observado; docs inconsistentes.",
    ),

    # ════════════════════════════════════════════════════════════════════
    # ROJO — 20 archetypes (RF-01..RF-04 force rojo, or score > 75)
    # ════════════════════════════════════════════════════════════════════

    # RF-01: PTxRB coverage → forced rojo
    ClaimArchetype(
        label="rojo-rf01-01",
        target_signals=["RF-01"],
        ramo="Vehículos", cobertura="Pérdida Total por Robo",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=1.00, suma_asegurada=35_000.0,
        es_robo=True, es_cobertura_ptxrb=True, demora_denuncia_horas=10.0,
        reporte_delay_days=1,
        descripcion="Pérdida total del vehículo por robo; cobertura PTxRB activada.",
    ),
    ClaimArchetype(
        label="rojo-rf01-02",
        target_signals=["RF-01"],
        ramo="Vehículos", cobertura="Pérdida Total por Robo",
        ciudad="Quito", estado="Reserva",
        monto_ratio=1.00, suma_asegurada=45_000.0,
        es_robo=True, es_cobertura_ptxrb=True, demora_denuncia_horas=8.0,
        reporte_delay_days=1,
        descripcion="Vehículo de alta gama hurtado; cobertura PTxRB activa.",
    ),
    ClaimArchetype(
        label="rojo-rf01-03",
        target_signals=["RF-01", "FS-02", "RF-06"],
        ramo="Vehículos", cobertura="Pérdida Total por Robo",
        ciudad="Manta", estado="Reserva",
        monto_ratio=1.00, suma_asegurada=30_000.0,
        es_robo=True, es_cobertura_ptxrb=True,
        demora_denuncia_horas=130.0,   # FS-02 + RF-06
        reporte_delay_days=6,
        descripcion="Vehículo robado; PTxRB con denuncia tardía.",
    ),
    ClaimArchetype(
        label="rojo-rf01-04",
        target_signals=["RF-01", "FS-03", "FS-14"],
        ramo="Vehículos", cobertura="Pérdida Total por Robo",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=1.00, suma_asegurada=40_000.0,
        es_robo=True, es_cobertura_ptxrb=True, demora_denuncia_horas=20.0,
        historial_siniestros_asegurado=3,  # FS-03
        reporte_delay_days=1,
        descripcion="PTxRB + asegurado con historial alto + monto total.",
    ),

    # RF-02: document falsification → forced rojo
    ClaimArchetype(
        label="rojo-rf02-01",
        target_signals=["FS-11", "RF-02"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.70, suma_asegurada=25_000.0,
        falsificacion_evidente=True, inconsistencia_documental=True,
        reporte_delay_days=6,
        descripcion="Alteración evidente en el informe de peritaje presentado.",
    ),
    ClaimArchetype(
        label="rojo-rf02-02",
        target_signals=["FS-11", "RF-02"],
        ramo="Incendio", cobertura="Todo Riesgo",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.85, suma_asegurada=80_000.0,
        falsificacion_evidente=True, inconsistencia_documental=True,
        reporte_delay_days=8,
        descripcion="Informe pericial falsificado con fechas manipuladas.",
    ),
    ClaimArchetype(
        label="rojo-rf02-03",
        target_signals=["FS-03", "FS-11", "RF-02"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.75, suma_asegurada=22_000.0,
        falsificacion_evidente=True, inconsistencia_documental=True,
        historial_siniestros_asegurado=4,  # FS-03
        reporte_delay_days=9,
        descripcion="Historial elevado + documentación falsificada.",
    ),

    # RF-03: restrictive list match → forced rojo
    ClaimArchetype(
        label="rojo-rf03-01",
        target_signals=["FS-07", "RF-03"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Esmeraldas", estado="Reserva",
        monto_ratio=0.60, suma_asegurada=18_000.0,
        proveedor="Mega Repuestos Cordero",
        proveedor_en_lista_restrictiva=True,
        reporte_delay_days=2,
        descripcion="Taller en lista restrictiva con alertas previas.",
    ),
    ClaimArchetype(
        label="rojo-rf03-02",
        target_signals=["RF-03"],
        ramo="Vida", cobertura="Muerte Natural",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.90, suma_asegurada=50_000.0,
        beneficiario_en_lista_restrictiva=True,
        reporte_delay_days=5,
        descripcion="Beneficiario en lista de monitoreo antilavado.",
    ),
    ClaimArchetype(
        label="rojo-rf03-03",
        target_signals=["FS-07", "RF-03"],
        ramo="Vida", cobertura="Muerte Accidental",
        ciudad="Machala", estado="Reserva",
        monto_ratio=0.80, suma_asegurada=40_000.0,
        beneficiario_en_lista_restrictiva=True,
        reporte_delay_days=3,
        descripcion="Beneficiario identificado en lista de alerta antilavado.",
    ),
    ClaimArchetype(
        label="rojo-rf03-04",
        target_signals=["FS-07", "FS-08", "RF-03"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.65, suma_asegurada=20_000.0,
        proveedor="Carrocerías Aguilera y Hnos",
        proveedor_en_lista_restrictiva=True,
        documentos_incompletos=True,
        docs_faltantes=["Denuncia", "Licencia"],
        reporte_delay_days=2,
        descripcion="Proveedor restrictivo + documentación incompleta.",
    ),

    # RF-04: impossible dynamics → forced rojo
    ClaimArchetype(
        label="rojo-rf04-01",
        target_signals=["RF-04"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.75, suma_asegurada=24_000.0,
        dinamica_imposible=True,
        reporte_delay_days=2,
        descripcion="Perito determina dinámica físicamente imposible.",
    ),
    ClaimArchetype(
        label="rojo-rf04-02",
        target_signals=["RF-04"],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.80, suma_asegurada=30_000.0,
        dinamica_imposible=True,
        reporte_delay_days=3,
        descripcion="Daños inconsistentes con trayectoria declarada.",
    ),
    ClaimArchetype(
        label="rojo-rf04-03",
        target_signals=["FS-09", "RF-04"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.90, suma_asegurada=26_000.0,
        dinamica_imposible=True, narrativa_ilógica=True,
        reporte_delay_days=4,
        descripcion="Narrativa incoherente; dinámica imposible confirmada por perito.",
    ),

    # High-score composites → score > 75
    ClaimArchetype(
        label="rojo-composite-01",
        target_signals=["FS-03", "FS-07", "FS-08", "FS-11", "FS-12", "RF-02"],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.88, suma_asegurada=32_000.0,
        historial_siniestros_asegurado=4,  # FS-03: 8 pts
        proveedor="Carrocerías Aguilera y Hnos",
        proveedor_en_lista_restrictiva=True,  # FS-07: 10 pts
        documentos_incompletos=True,
        falsificacion_evidente=True, inconsistencia_documental=True,  # FS-11: 10 pts, RF-02
        docs_faltantes=["Denuncia", "Licencia"],  # FS-08: 4 pts
        reporte_delay_days=9,  # FS-12: 5 pts → 37 pts + RF-02 → rojo
        descripcion="Historial elevado; proveedor restrictivo; docs falsificados; reporte tardío.",
    ),
    ClaimArchetype(
        label="rojo-composite-02",
        target_signals=["FS-01", "FS-03", "FS-05", "FS-10", "FS-14"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=25_000.0,
        dias_desde_inicio_poliza=5,        # FS-01: 8 pts
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        frecuencia_conductor=3,            # FS-05: 8 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts → 35 pts verde... need RF
        reporte_delay_days=2,
        descripcion="Inicio póliza + asegurado+conductor frecuentes + daño sin testigos.",
    ),
    ClaimArchetype(
        label="rojo-score-high-01",
        target_signals=[
            "FS-01", "FS-03", "FS-04", "FS-05", "FS-07", "FS-09", "FS-10", "FS-11", "FS-12",
        ],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.85, suma_asegurada=35_000.0,
        dias_desde_inicio_poliza=7,        # FS-01: 8 pts
        historial_siniestros_asegurado=4,  # FS-03: 8 pts
        frecuencia_vehiculo=3,             # FS-04: 6 pts
        frecuencia_conductor=4,            # FS-05: 8 pts
        proveedor="Reparaciones Río Verde",
        proveedor_casos_observados=4,      # FS-07: 5 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        reporte_delay_days=9,              # FS-12: 5 pts → 57 pts → amarillo
        descripcion="Máxima acumulación: inicio póliza + 4 frecuencias + proveedor + extras.",
    ),
    ClaimArchetype(
        label="rojo-score-high-02",
        target_signals=[
            "FS-01", "FS-03", "FS-04", "FS-05", "FS-07",
            "FS-08", "FS-09", "FS-10", "FS-11", "FS-12", "FS-14",
        ],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=40_000.0,
        dias_desde_inicio_poliza=5,        # FS-01: 8 pts
        historial_siniestros_asegurado=5,  # FS-03: 8 pts
        frecuencia_vehiculo=4,             # FS-04: 6 pts
        frecuencia_conductor=5,            # FS-05: 8 pts
        proveedor="Taller Mecánico Vergara",
        proveedor_en_lista_restrictiva=True,  # FS-07: 10 pts
        documentos_incompletos=True,
        docs_faltantes=["Denuncia", "Matrícula"],  # FS-08: 4 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        reporte_delay_days=10,             # FS-12: 5 pts → 76 pts → rojo!
        descripcion="Caso de máximo riesgo: 11 señales acumuladas.",
    ),
    ClaimArchetype(
        label="rojo-score-high-03",
        target_signals=[
            "FS-03", "FS-04", "FS-05", "FS-06", "FS-07",
            "FS-08", "FS-09", "FS-10", "FS-11", "FS-13", "FS-14",
        ],
        ramo="Vehículos", cobertura="Responsabilidad Civil",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=18_000.0,
        historial_siniestros_asegurado=5,  # FS-03: 8 pts
        frecuencia_vehiculo=4,             # FS-04: 6 pts
        frecuencia_conductor=5,            # FS-05: 8 pts
        eventos_rc_previos=4,              # FS-06: 6 pts
        proveedor="Reparaciones Salvador",
        proveedor_en_lista_restrictiva=True,  # FS-07: 10 pts
        documentos_incompletos=True,
        docs_faltantes=["Proforma"],       # FS-08: 4 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        narrativa_similar_score=0.87,      # FS-13: 8 pts
        cobertura_rc=True,                 # FS-14: 5 pts → 78 pts → rojo!
        reporte_delay_days=3,
        descripcion="Caso RC con 11 señales acumuladas; score 78 pts.",
    ),
    ClaimArchetype(
        label="rojo-fs13-highsim",
        target_signals=["FS-03", "FS-07", "FS-10", "FS-11", "FS-13", "FS-14"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=28_000.0,
        historial_siniestros_asegurado=4,  # FS-03: 8 pts
        proveedor="Carrocerías El Inca",
        proveedor_casos_observados=4,      # FS-07: 5 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        narrativa_similar_score=0.88,      # FS-13: 8 pts → 37 pts verde (need RF to push rojo)
        reporte_delay_days=2,
        descripcion="Narrativa muy similar + proveedor + inconsistencias documentales.",
    ),

    # ════════════════════════════════════════════════════════════════════
    # ENRIQUECIMIENTO — nuevas ciudades, ramos y patrones Ecuador
    # ════════════════════════════════════════════════════════════════════

    # ── Nuevos VERDE (diversidad geográfica y ramos) ──────────────────
    ClaimArchetype(
        label="verde-clean-santo-domingo",
        target_signals=[],
        ramo="Vehículos", cobertura="Daños Parciales",
        ciudad="Santo Domingo", estado="Liquidado",
        monto_ratio=0.12, suma_asegurada=15_500.0,
        descripcion="Raspón lateral en redondel vial. Sin lesionados. Taller autorizado.",
    ),
    ClaimArchetype(
        label="verde-clean-ibarra",
        target_signals=[],
        ramo="Accidentes Personales", cobertura="Cobertura Básica",
        ciudad="Ibarra", estado="Pago Total",
        monto_ratio=0.08, suma_asegurada=9_000.0,
        descripcion="Caída de motociclista; documentación completa; lesión leve.",
    ),
    ClaimArchetype(
        label="verde-clean-riobamba",
        target_signals=[],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Riobamba", estado="Pago Parcial",
        monto_ratio=0.14, suma_asegurada=13_000.0,
        descripcion="Colisión menor en intersección urbana de Riobamba.",
    ),
    ClaimArchetype(
        label="verde-clean-latacunga",
        target_signals=[],
        ramo="Incendio", cobertura="Incendio y Líneas Aliadas",
        ciudad="Latacunga", estado="Liquidado",
        monto_ratio=0.07, suma_asegurada=45_000.0,
        descripcion="Cortocircuito en instalación eléctrica; daños menores; póliza vigente.",
    ),

    # ── Nuevos AMARILLO (patrones de fraude adicionales en Ecuador) ───
    ClaimArchetype(
        label="amarillo-hilux-robo-riobamba",
        target_signals=["FS-02", "FS-03", "RF-06"],
        ramo="Vehículos", cobertura="Robo Total",
        ciudad="Riobamba", estado="Reserva",
        monto_ratio=0.95, suma_asegurada=42_000.0,
        es_robo=True, demora_denuncia_horas=105.0,   # RF-06
        historial_siniestros_asegurado=3,             # FS-03: 8 pts
        reporte_delay_days=5,
        descripcion=(
            "Toyota Hilux robada en zona periférica de Riobamba. "
            "Propietario reportó la sustracción 4 días después del hecho."
        ),
    ),
    ClaimArchetype(
        label="amarillo-stacked-santo-domingo",
        target_signals=["FS-01", "FS-05", "FS-08", "FS-12"],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Santo Domingo", estado="Reserva",
        monto_ratio=0.55, suma_asegurada=22_000.0,
        dias_desde_inicio_poliza=7,    # FS-01: 8 pts
        frecuencia_conductor=3,        # FS-05: 8 pts
        documentos_incompletos=True,
        docs_faltantes=["Denuncia policial"],  # FS-08: 4 pts
        reporte_delay_days=9,          # FS-12: 5 pts → 25 pts
        descripcion=(
            "Siniestro en semana de vigencia de póliza; conductor con historial; "
            "falta denuncia policial; reporte con nueve días de demora."
        ),
    ),
    ClaimArchetype(
        label="amarillo-dmx-pickup-peritaje",
        target_signals=["FS-05", "FS-07", "FS-10", "FS-14"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Quevedo", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=32_000.0,
        frecuencia_conductor=3,        # FS-05: 8 pts
        proveedor="Taller Av. de los Shyris",
        proveedor_casos_observados=3,  # FS-07: 5 pts
        sin_rastro_tercero=True,       # FS-10: 6 pts → 24 pts
        reporte_delay_days=2,
        descripcion=(
            "Chevrolet D-Max con daños extensos; peritaje indica impacto frontal "
            "sin evidencia de tercero en la escena."
        ),
    ),
    ClaimArchetype(
        label="amarillo-incendio-ibarra",
        target_signals=["FS-08", "FS-11", "FS-12", "RF-07"],
        ramo="Incendio", cobertura="Todo Riesgo",
        ciudad="Ibarra", estado="Reserva",
        monto_ratio=0.80, suma_asegurada=55_000.0,
        documentos_incompletos=True,
        docs_faltantes=["Informe del cuerpo de bomberos", "Peritaje"],  # FS-08: 4 pts
        inconsistencia_documental=True,   # FS-11: 5 pts
        reporte_delay_days=8,             # FS-12: 5 pts
        narrativa_similar_score=0.99, narrativa_clonada=True,   # RF-07
        descripcion=(
            "Incendio en bodega de comercio en Ibarra. "
            "Falta informe de bomberos; peritaje con inconsistencias; "
            "narrativa idéntica a siniestro anterior."
        ),
    ),
    ClaimArchetype(
        label="amarillo-rc-milagro",
        target_signals=["FS-03", "FS-06", "FS-07", "FS-12"],
        ramo="Vehículos", cobertura="Responsabilidad Civil",
        ciudad="Milagro", estado="Reserva",
        monto_ratio=0.40, suma_asegurada=10_000.0,
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        eventos_rc_previos=3,              # FS-06: 6 pts
        proveedor="Servicios Automotrices Calderón",
        proveedor_casos_observados=3,      # FS-07: 5 pts
        reporte_delay_days=8,              # FS-12: 5 pts → 24 pts
        cobertura_rc=True,
        descripcion=(
            "Tercer evento RC para el asegurado en 18 meses; "
            "proveedor vinculado a reclamaciones observadas en zona de Milagro."
        ),
    ),
    ClaimArchetype(
        label="amarillo-carga-transporte",
        target_signals=["FS-01", "FS-03", "FS-08", "FS-09"],
        ramo="Transporte", cobertura="Mercancías en Tránsito",
        ciudad="Babahoyo", estado="Reserva",
        monto_ratio=0.65, suma_asegurada=18_000.0,
        dias_desde_inicio_poliza=7,        # FS-01: 8 pts
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        documentos_incompletos=True,
        docs_faltantes=["Guía de remisión", "Foto de carga"],  # FS-08: 4 pts
        narrativa_ilógica=True,            # FS-09: 6 pts → 26 pts
        reporte_delay_days=3,
        descripcion=(
            "Pérdida de mercancía agrícola en ruta Babahoyo-Guayaquil. "
            "Póliza con 5 días de vigencia; guía de remisión ausente; "
            "ruta declarada inconsistente con GPS."
        ),
    ),

    # ── Nuevos ROJO (patrones de alto riesgo Ecuador) ─────────────────
    ClaimArchetype(
        label="rojo-red-talleres-guayaquil",
        target_signals=["FS-03", "FS-05", "FS-07", "FS-09", "FS-13", "RF-03"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.75, suma_asegurada=24_000.0,
        historial_siniestros_asegurado=4,  # FS-03: 8 pts
        frecuencia_conductor=3,            # FS-05: 8 pts
        proveedor="Carrocerías Toral",
        proveedor_en_lista_restrictiva=True,  # RF-03 + FS-07: 10 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        narrativa_similar_score=0.87,      # FS-13: 8 pts
        reporte_delay_days=3,
        descripcion=(
            "Siniestro derivado a taller en lista restrictiva. "
            "Conductor con múltiples reclamaciones previas; "
            "narrativa muy similar a otro caso reciente."
        ),
    ),
    ClaimArchetype(
        label="rojo-abandono-vehiculo-quito",
        target_signals=["RF-01", "FS-02", "FS-03", "FS-12"],
        ramo="Vehículos", cobertura="Pérdida Total por Robo",
        ciudad="Quito", estado="Reserva",
        monto_ratio=1.00, suma_asegurada=38_000.0,
        es_robo=True, es_cobertura_ptxrb=True,
        demora_denuncia_horas=25.0,        # FS-02 mid
        historial_siniestros_asegurado=3,  # FS-03: 8 pts
        reporte_delay_days=7,              # FS-12: 5 pts; RF-01 fuerza rojo
        descripcion=(
            "Toyota Prado reportada robada en Quito Norte. "
            "Asegurado con dos PTxRB en últimos 24 meses; "
            "denuncia ante el ECU-911 con 25 horas de demora."
        ),
    ),
    ClaimArchetype(
        label="rojo-montaje-accidente-ibarra",
        target_signals=["RF-04", "FS-05", "FS-09", "FS-11", "FS-13"],
        ramo="Vehículos", cobertura="Colisión",
        ciudad="Ibarra", estado="Reserva",
        monto_ratio=0.88, suma_asegurada=20_000.0,
        dinamica_imposible=True,           # RF-04 → rojo
        frecuencia_conductor=3,            # FS-05: 8 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        narrativa_similar_score=0.91,      # FS-13: 8 pts
        reporte_delay_days=4,
        descripcion=(
            "Perito determina que los daños son incompatibles con la dinámica declarada. "
            "Conductor con historial; documentos con fechas alteradas; "
            "descripción casi idéntica a caso SIN-F045."
        ),
    ),
    ClaimArchetype(
        label="rojo-score-high-04",
        target_signals=[
            "FS-01", "FS-03", "FS-04", "FS-05", "FS-07",
            "FS-08", "FS-09", "FS-10", "FS-11", "FS-12", "FS-14",
        ],
        ramo="Vehículos", cobertura="Todo Riesgo",
        ciudad="Santo Domingo", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=35_000.0,
        dias_desde_inicio_poliza=5,        # FS-01: 8 pts
        historial_siniestros_asegurado=5,  # FS-03: 8 pts
        frecuencia_vehiculo=4,             # FS-04: 6 pts
        frecuencia_conductor=4,            # FS-05: 8 pts
        proveedor="Multitalleres Espinoza",
        proveedor_en_lista_restrictiva=True,  # FS-07: 10 pts
        documentos_incompletos=True,
        docs_faltantes=["Denuncia", "Matrícula"],  # FS-08: 4 pts
        narrativa_ilógica=True,            # FS-09: 6 pts
        sin_rastro_tercero=True,           # FS-10: 6 pts
        inconsistencia_documental=True,    # FS-11: 5 pts
        reporte_delay_days=10,             # FS-12: 5 pts → 76 pts → rojo
        descripcion=(
            "Caso de máximo riesgo en Santo Domingo: 11 señales simultáneas. "
            "Póliza reciente; alta frecuencia vehículo+conductor+asegurado; "
            "taller en lista restrictiva; documentos incompletos e inconsistentes."
        ),
    ),
    ClaimArchetype(
        label="rojo-falsificacion-riobamba",
        target_signals=["FS-03", "FS-11", "FS-12", "RF-02"],
        ramo="Vehículos", cobertura="Daños",
        ciudad="Riobamba", estado="Reserva",
        monto_ratio=0.78, suma_asegurada=21_000.0,
        falsificacion_evidente=True, inconsistencia_documental=True,  # RF-02 → rojo
        historial_siniestros_asegurado=4,  # FS-03: 8 pts
        reporte_delay_days=9,              # FS-12: 5 pts
        descripcion=(
            "Peritaje con sello falsificado detectado por auditoría interna. "
            "Asegurado con cuatro siniestros previos; informe con fechas inconsistentes."
        ),
    ),

    # ════════════════════════════════════════════════════════════════════
    # DIVERSIDAD DE RAMOS — Salud / Hogar / Vida / Generales
    # Hasta acá la mayoría de arquetipos son Vehículos. Esta sección
    # introduce ramos no-vehículo para que el dashboard de proveedores y
    # la tarjeta "Alertas por ramo" muestren la diversidad real del libro.
    # Cada arquetipo dispara señales del catálogo FS/RF sin romper la
    # cobertura existente.
    # ════════════════════════════════════════════════════════════════════

    # ── SALUD ────────────────────────────────────────────────────────────
    ClaimArchetype(
        label="verde-salud-hospitalizacion-ambato",
        target_signals=[],
        ramo="Salud", cobertura="Hospitalización",
        ciudad="Ambato", estado="Pago Total",
        monto_ratio=0.30, suma_asegurada=12_000.0,
        descripcion=(
            "Hospitalización por apendicitis con cobertura quirúrgica. "
            "Documentación clínica completa; alta sin complicaciones."
        ),
    ),
    ClaimArchetype(
        label="verde-salud-consulta-quito",
        target_signals=["FS-12"],
        ramo="Salud", cobertura="Consulta Ambulatoria",
        ciudad="Quito", estado="Pago Parcial",
        monto_ratio=0.22, suma_asegurada=6_500.0,
        reporte_delay_days=5,   # mid: 3 pts, stays verde
        descripcion=(
            "Consulta especializada en cardiología; factura presentada cinco días después."
        ),
    ),
    ClaimArchetype(
        label="amarillo-salud-clinica-recurrente",
        target_signals=["FS-03", "FS-07", "FS-08"],
        ramo="Salud", cobertura="Hospitalización",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.55, suma_asegurada=16_000.0,
        historial_siniestros_asegurado=3,   # FS-03: 8 pts
        proveedor="Clínica Kennedy Norte",
        proveedor_casos_observados=4,        # FS-07: 5 pts
        documentos_incompletos=True,
        docs_faltantes=["Historia clínica", "Receta"],  # FS-08: 4 pts → 17 pts
        reporte_delay_days=2,
        descripcion=(
            "Asegurado con múltiples hospitalizaciones en la misma clínica este año. "
            "Historia clínica detallada no aportada; receta médica pendiente."
        ),
    ),
    ClaimArchetype(
        label="amarillo-salud-dx-inconsistente",
        target_signals=["FS-09", "FS-11", "FS-12"],
        ramo="Salud", cobertura="Atención Quirúrgica",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.70, suma_asegurada=18_000.0,
        proveedor="Hospital del Río Cuenca",
        narrativa_ilógica=True,             # FS-09: 6 pts
        inconsistencia_documental=True,      # FS-11: 5 pts
        reporte_delay_days=8,                # FS-12: 5 pts → 16 pts
        descripcion=(
            "Diagnóstico declarado no coincide con los procedimientos facturados. "
            "Fechas del informe quirúrgico previas al ingreso del paciente."
        ),
    ),
    ClaimArchetype(
        label="rojo-salud-rf02-quito",
        target_signals=["FS-03", "FS-11", "RF-02"],
        ramo="Salud", cobertura="Hospitalización",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.90, suma_asegurada=28_000.0,
        proveedor="Hospital Metropolitano de Quito",
        falsificacion_evidente=True, inconsistencia_documental=True,  # RF-02 → rojo
        historial_siniestros_asegurado=4,   # FS-03: 8 pts
        reporte_delay_days=6,
        descripcion=(
            "Factura hospitalaria con sello adulterado detectado en auditoría. "
            "Asegurado con cuatro hospitalizaciones previas en 18 meses."
        ),
    ),
    ClaimArchetype(
        label="rojo-salud-rf03-beneficiario-listado",
        target_signals=["FS-07", "RF-03"],
        ramo="Salud", cobertura="Reembolso Médico",
        ciudad="Manta", estado="Reserva",
        monto_ratio=0.85, suma_asegurada=20_000.0,
        proveedor="Centro Médico Latacunga",
        proveedor_en_lista_restrictiva=True,   # RF-03 → rojo
        reporte_delay_days=4,
        descripcion=(
            "Centro médico identificado en lista restrictiva por reclamaciones "
            "observadas en regional Costa; reembolso por consultas no respaldadas."
        ),
    ),

    # ── HOGAR ────────────────────────────────────────────────────────────
    ClaimArchetype(
        label="verde-hogar-fuga-agua",
        target_signals=[],
        ramo="Hogar", cobertura="Daños por Agua",
        ciudad="Quito", estado="Liquidado",
        monto_ratio=0.18, suma_asegurada=22_000.0,
        descripcion=(
            "Fuga en cañería de cocina; daño localizado en gabinetes inferiores. "
            "Peritaje rápido; documentación completa."
        ),
    ),
    ClaimArchetype(
        label="amarillo-hogar-incendio-rf05",
        target_signals=["FS-01", "FS-08", "RF-05"],
        ramo="Hogar", cobertura="Incendio y Líneas Aliadas",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.70, suma_asegurada=60_000.0,
        proveedor="Restauraciones Costa Norte",
        dias_desde_inicio_poliza=1,         # RF-05 → amarillo floor
        documentos_incompletos=True,
        docs_faltantes=["Informe de bomberos"],  # FS-08: 4 pts
        reporte_delay_days=2,
        descripcion=(
            "Incendio declarado al segundo día de vigencia de la póliza de hogar. "
            "Informe de bomberos no entregado al momento del reclamo."
        ),
    ),
    ClaimArchetype(
        label="amarillo-hogar-robo-edge",
        target_signals=["FS-02", "FS-12", "RF-06"],
        ramo="Hogar", cobertura="Robo Domiciliario",
        ciudad="Cuenca", estado="Reserva",
        monto_ratio=0.55, suma_asegurada=25_000.0,
        proveedor="Peritaje y Restauración Cuenca",
        es_robo=True, demora_denuncia_horas=120.0,   # RF-06
        reporte_delay_days=6,                          # FS-12: 3 pts
        descripcion=(
            "Robo en vivienda con denuncia ante la policía cinco días después. "
            "Inventario presentado de memoria, sin facturas de respaldo."
        ),
    ),
    ClaimArchetype(
        label="rojo-hogar-rf02-falsificacion",
        target_signals=["FS-08", "FS-11", "FS-14", "RF-02"],
        ramo="Hogar", cobertura="Incendio y Líneas Aliadas",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=80_000.0,
        proveedor="Restauradora Hogar Seguro",
        falsificacion_evidente=True, inconsistencia_documental=True,  # RF-02 → rojo
        documentos_incompletos=True,
        docs_faltantes=["Avalúo independiente"],   # FS-08: 4 pts
        reporte_delay_days=5,
        descripcion=(
            "Incendio en bodega doméstica con facturas de avalúo alteradas. "
            "Monto reclamado prácticamente igual a la suma asegurada."
        ),
    ),
    ClaimArchetype(
        label="rojo-hogar-rf03-restaurador",
        target_signals=["FS-07", "FS-11", "RF-03"],
        ramo="Hogar", cobertura="Daños por Agua",
        ciudad="Manta", estado="Reserva",
        monto_ratio=0.80, suma_asegurada=35_000.0,
        proveedor="Servicios Integrales del Hogar Quito",
        proveedor_en_lista_restrictiva=True,   # RF-03 → rojo
        inconsistencia_documental=True,         # FS-11: 5 pts
        reporte_delay_days=4,
        descripcion=(
            "Restaurador en lista restrictiva por reclamaciones recurrentes. "
            "Cotización original modificada después del primer peritaje."
        ),
    ),

    # ── VIDA ─────────────────────────────────────────────────────────────
    ClaimArchetype(
        label="verde-vida-muerte-natural",
        target_signals=[],
        ramo="Vida", cobertura="Muerte Natural",
        ciudad="Cuenca", estado="Pago Total",
        monto_ratio=1.00, suma_asegurada=30_000.0,
        proveedor="Funeraria San Pedro Cuenca",
        reporte_delay_days=10,
        descripcion=(
            "Fallecimiento por causas naturales de asegurado de 72 años. "
            "Certificado médico legal y partida de defunción en regla."
        ),
    ),
    ClaimArchetype(
        label="amarillo-vida-fs01-edge",
        target_signals=["FS-01", "FS-12", "RF-05"],
        ramo="Vida", cobertura="Muerte Accidental",
        ciudad="Quito", estado="Reserva",
        monto_ratio=1.00, suma_asegurada=50_000.0,
        proveedor="Funeraria Memorial Quito",
        dias_desde_inicio_poliza=1,         # RF-05 → amarillo
        reporte_delay_days=15,              # FS-12: 5 pts
        descripcion=(
            "Fallecimiento accidental dos días después del inicio de vigencia. "
            "Aviso al asegurador presentado dos semanas después del evento."
        ),
    ),
    ClaimArchetype(
        label="amarillo-vida-doble-cobertura",
        target_signals=["FS-03", "FS-12", "FS-14"],
        ramo="Vida", cobertura="Muerte Accidental",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=45_000.0,
        proveedor="Asesoría Legal Memorial Guayaquil",
        historial_siniestros_asegurado=3,   # FS-03: 8 pts
        reporte_delay_days=12,              # FS-12: 5 pts → 13 pts
        descripcion=(
            "Beneficiario con tres reclamaciones de vida previas; "
            "monto cercano a la suma asegurada en pólizas duplicadas."
        ),
    ),
    ClaimArchetype(
        label="rojo-vida-rf03-lavado",
        target_signals=["FS-07", "RF-03"],
        ramo="Vida", cobertura="Muerte Natural",
        ciudad="Manta", estado="Reserva",
        monto_ratio=0.95, suma_asegurada=60_000.0,
        proveedor="Funeraria Pacífico Manta",
        beneficiario_en_lista_restrictiva=True,   # RF-03 → rojo
        reporte_delay_days=4,
        descripcion=(
            "Beneficiario aparece en lista de monitoreo antilavado. "
            "Funeraria asociada también presenta reclamaciones observadas."
        ),
    ),
    ClaimArchetype(
        label="rojo-vida-rf02-certificado",
        target_signals=["FS-11", "FS-12", "RF-02"],
        ramo="Vida", cobertura="Muerte Accidental",
        ciudad="Riobamba", estado="Reserva",
        monto_ratio=1.00, suma_asegurada=55_000.0,
        proveedor="Médico Legal Centro Riobamba",
        falsificacion_evidente=True, inconsistencia_documental=True,  # RF-02 → rojo
        reporte_delay_days=11,
        descripcion=(
            "Certificado de defunción con firmas y sellos adulterados según "
            "validación notarial; reporte tardío al asegurador."
        ),
    ),

    # ── GENERALES (Transporte / Equipo / Comercial) ──────────────────────
    ClaimArchetype(
        label="verde-generales-equipo-electronico",
        target_signals=[],
        ramo="Equipo Electrónico", cobertura="Daño Súbito",
        ciudad="Quito", estado="Pago Parcial",
        monto_ratio=0.25, suma_asegurada=18_000.0,
        proveedor="Servicios Electrónicos Industriales Quito",
        descripcion=(
            "Daño súbito en servidor de oficina por descarga eléctrica. "
            "Peritaje técnico completo; reparación parcial autorizada."
        ),
    ),
    ClaimArchetype(
        label="amarillo-generales-transporte-fs08",
        target_signals=["FS-01", "FS-08", "FS-09"],
        ramo="Transporte", cobertura="Mercancías en Tránsito",
        ciudad="Babahoyo", estado="Reserva",
        monto_ratio=0.65, suma_asegurada=22_000.0,
        proveedor="Logística Andina Carga",
        dias_desde_inicio_poliza=7,         # FS-01: 8 pts
        documentos_incompletos=True,
        docs_faltantes=["Guía de remisión", "Bill of lading"],  # FS-08: 4 pts
        narrativa_ilógica=True,             # FS-09: 6 pts → 18 pts
        reporte_delay_days=3,
        descripcion=(
            "Pérdida de mercancía en tránsito Babahoyo-Guayaquil con póliza "
            "recién emitida; guía de remisión y BL ausentes; ruta declarada "
            "inconsistente con GPS de la flota."
        ),
    ),
    ClaimArchetype(
        label="amarillo-generales-equipo-rf07",
        target_signals=["FS-13", "RF-07"],
        ramo="Equipo Electrónico", cobertura="Robo",
        ciudad="Guayaquil", estado="Reserva",
        monto_ratio=0.55, suma_asegurada=24_000.0,
        proveedor="Reparaciones Industriales Cuenca",
        narrativa_similar_score=0.98, narrativa_clonada=True,   # RF-07 → amarillo
        reporte_delay_days=2,
        descripcion=(
            "Robo de equipo informático en oficina; narrativa idéntica a "
            "reclamo previo SIN-G021 reportado tres meses antes."
        ),
    ),
    ClaimArchetype(
        label="amarillo-generales-rc-comercial",
        target_signals=["FS-03", "FS-06", "FS-12"],
        ramo="Responsabilidad Civil Comercial", cobertura="Daños a Terceros",
        ciudad="Loja", estado="Reserva",
        monto_ratio=0.45, suma_asegurada=20_000.0,
        proveedor="Ajustadores y Peritos del Sur",
        historial_siniestros_asegurado=3,   # FS-03: 8 pts
        eventos_rc_previos=3,                # FS-06: 6 pts
        reporte_delay_days=8,                # FS-12: 5 pts → 19 pts
        descripcion=(
            "Tercera reclamación RC del comercio en 18 meses; "
            "aviso al asegurador con ocho días de demora."
        ),
    ),
    ClaimArchetype(
        label="rojo-generales-transporte-rf02",
        target_signals=["FS-08", "FS-11", "FS-14", "RF-02"],
        ramo="Transporte", cobertura="Mercancías en Tránsito",
        ciudad="Manta", estado="Reserva",
        monto_ratio=0.97, suma_asegurada=70_000.0,
        proveedor="Carga Express Guayaquil-Manta",
        falsificacion_evidente=True, inconsistencia_documental=True,  # RF-02 → rojo
        documentos_incompletos=True,
        docs_faltantes=["Conduce camión"],   # FS-08: 4 pts
        reporte_delay_days=5,
        descripcion=(
            "Pérdida total de carga marítima con facturas comerciales alteradas. "
            "Conduce del camión ausente; monto cercano a la suma asegurada."
        ),
    ),
    ClaimArchetype(
        label="rojo-generales-fianzas-rf03",
        target_signals=["FS-07", "FS-11", "RF-03"],
        ramo="Fianzas", cobertura="Cumplimiento de Contrato",
        ciudad="Quito", estado="Reserva",
        monto_ratio=0.90, suma_asegurada=50_000.0,
        proveedor="Peritaje Comercial Pacífico",
        proveedor_en_lista_restrictiva=True,   # RF-03 → rojo
        inconsistencia_documental=True,         # FS-11: 5 pts
        reporte_delay_days=6,
        descripcion=(
            "Ejecución de fianza de cumplimiento con perito en lista restrictiva. "
            "Acta de incumplimiento con fechas inconsistentes con cronograma."
        ),
    ),
]
