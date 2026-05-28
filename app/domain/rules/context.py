"""RuleContext — derived signals beyond ClaimDetail that rules consume.

``from_claim`` derives what it can from ClaimDetail and defaults the rest to
safe non-firing values so rules can be evaluated without a full DB round-trip
(useful for the fire-test endpoint and smoke tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.claim import ClaimDetail


@dataclass
class RuleContext:
    # ── temporal derivations (auto-derived from ClaimDetail) ──────────────────
    dias_entre_ocurrencia_reporte: int = 0  # (fecha_reporte - fecha_ocurrencia).days

    # ── policy proximity (auto-derived if policy dates are available) ─────────
    dias_desde_inicio_poliza: int = 9999   # days from policy start to occurrence
    dias_desde_fin_poliza: int = 9999      # days from occurrence to policy end

    # ── frequency signals (populated by score_claim from repo context) ────────
    historial_siniestros_asegurado: int = 0   # claims in last 18 months (insured)
    frecuencia_vehiculo: int = 0               # prior claims for same vehicle
    frecuencia_conductor: int = 0              # prior claims for same driver
    eventos_rc_previos: int = 0               # prior RC-only events

    # ── provider / beneficiary ───────────────────────────────────────────────
    proveedor_en_lista_restrictiva: bool = False
    beneficiario_en_lista_restrictiva: bool = False
    proveedor_casos_observados: int = 0        # historical claims tied to provider

    # ── document quality ──────────────────────────────────────────────────────
    documentos_incompletos: bool = False
    inconsistencia_documental: bool = False
    falsificacion_evidente: bool = False

    # ── narrative similarity (filled by the similarity layer, L7) ────────────
    narrativa_similar_score: float = 0.0      # top-1 cosine similarity [0, 1]
    narrativa_clonada: bool = False            # similarity >= RF_07 threshold

    # ── dynamics ─────────────────────────────────────────────────────────────
    dinamica_imposible: bool = False           # physically impossible accident
    sin_rastro_tercero: bool = False           # severe damage, no third-party trace
    evento_medianoche: bool = False            # midnight multi-event flag

    # ── financials (auto-derived) ─────────────────────────────────────────────
    monto_vs_suma_pct: float = 0.0             # monto_reclamado / suma_asegurada

    # ── coverage tag (for RF-01 theft total loss) ────────────────────────────
    es_cobertura_ptxrb: bool = False           # True if coverage = Pérdida Total por Robo

    # ── denouncement delay for theft (hours) ─────────────────────────────────
    demora_denuncia_horas: float = 0.0         # hours between ocurrencia and reporte

    # ── additional flags for FS-02 (applies only to theft) ───────────────────
    es_robo: bool = False                      # True if coverage involves theft

    # ── repair average comparison ─────────────────────────────────────────────
    monto_vs_reparacion_avg_pct: float = 0.0   # monto / avg_repair_cost for the vehicle class

    # ── RC coverage flag ─────────────────────────────────────────────────────
    cobertura_rc: bool = False                 # True if coverage = Responsabilidad Civil only

    # ── internal marker for FS-09 (illogical narrative) ──────────────────────
    narrativa_ilógica: bool = False            # pre-tagged by NLP layer; safe default = False

    # ── vehicle identity (FS-15) — filled by the decode step, not from_claim ──
    # True when the chassis/VIN decodes to a spec that contradicts the declared
    # vehicle. Needs the VehicleDecoder, so it is NOT derived in from_claim.
    vehiculo_inconsistente: bool = False
    vehiculo_campos_discrepantes: list[str] = field(default_factory=list)

    # ── extra meta ───────────────────────────────────────────────────────────
    extra: dict[str, object] = field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_claim(cls, claim: ClaimDetail) -> RuleContext:
        """Derive what we can from ClaimDetail; defaults everything else.

        When ``fecha_inicio_poliza`` / ``fecha_fin_poliza`` are present on the
        claim, the policy-proximity deltas are recomputed from actual dates so
        that patching ``fecha_ocurrencia`` (fire-test endpoint) re-fires FS-01
        and RF-05 correctly.  Falls back to 9999 (non-firing) when absent.
        """
        dias = (claim.fecha_reporte - claim.fecha_ocurrencia).days
        monto_pct = (
            claim.monto_reclamado / claim.suma_asegurada
            if claim.suma_asegurada > 0
            else 0.0
        )

        # Policy-proximity — re-derive when dates are available
        dias_desde_inicio = (
            (claim.fecha_ocurrencia - claim.fecha_inicio_poliza).days
            if claim.fecha_inicio_poliza is not None
            else 9999
        )
        dias_desde_fin = (
            (claim.fecha_fin_poliza - claim.fecha_ocurrencia).days
            if claim.fecha_fin_poliza is not None
            else 9999
        )

        # Coverage-based flags
        cobertura_lower = claim.cobertura.lower()
        es_robo = "robo" in cobertura_lower
        es_cobertura_ptxrb = (
            "pérdida total por robo" in cobertura_lower
            or "ptxrb" in cobertura_lower
            or "robo total" in cobertura_lower
            or "pérdida total robo" in cobertura_lower
        )

        # Denouncement delay in hours (only meaningful for theft)
        demora_denuncia_horas = float(dias * 24) if es_robo else 0.0

        # Document completeness — infer from ClaimDetail.documentos
        documentos_incompletos = any(d.falta for d in claim.documentos)

        # RC-only coverage
        cobertura_rc = "responsabilidad civil" in cobertura_lower

        return cls(
            dias_entre_ocurrencia_reporte=dias,
            dias_desde_inicio_poliza=dias_desde_inicio,
            dias_desde_fin_poliza=dias_desde_fin,
            monto_vs_suma_pct=monto_pct,
            es_robo=es_robo,
            es_cobertura_ptxrb=es_cobertura_ptxrb,
            demora_denuncia_horas=demora_denuncia_horas,
            documentos_incompletos=documentos_incompletos,
            cobertura_rc=cobertura_rc,
        )
