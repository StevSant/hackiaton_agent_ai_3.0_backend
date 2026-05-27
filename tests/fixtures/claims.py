"""Synthetic claim fixtures spanning the three triage tiers — no real PII (§2.10).

Used by rules/scoring tests (Track B) and route smoke tests (Track C) until the
synthetic generator (V1) lands. Keep these hand-crafted and small.
"""

from datetime import date

from app.schemas.claim import (
    ClaimAlert,
    ClaimDetail,
    ClaimDocument,
    ClaimReview,
    ClaimTimelineEvent,
    ClaimVehicle,
    ReviewStatus,
)
from app.schemas.risk import Tier


def claim_verde() -> ClaimDetail:
    """Clean claim — no rules fire, normal flow."""
    return ClaimDetail(
        id="SIN-0001",
        ramo="Vehículos",
        cobertura="Responsabilidad Civil",
        asegurado="A. Pérez",
        asegurado_id="ASE-1001",
        poliza="POL-5001",
        ciudad="Guayaquil",
        fecha_ocurrencia=date(2026, 3, 10),
        fecha_reporte=date(2026, 3, 11),
        monto_reclamado=1200.0,
        suma_asegurada=20000.0,
        estado="Reserva",
        sucursal="Guayaquil Centro",
        vehiculo=ClaimVehicle(marca="Chevrolet", modelo="Sail", anio=2019, placa="GAB-1234"),
        proveedor=None,
        descripcion="Choque leve en parqueo, daño en parachoques trasero.",
        score=18,
        nivel=Tier.verde,
        alertas=[],
        timeline=[ClaimTimelineEvent(date="2026-03-10", title="Ocurrencia", tone="ok")],
        documentos=[ClaimDocument(tipo="Denuncia", estado="Entregado")],
        review=ClaimReview(status=ReviewStatus.pendiente),
    )


def claim_amarillo() -> ClaimDetail:
    """Mid-risk — a couple of scored signals fire (near policy edge + report delay)."""
    return ClaimDetail(
        id="SIN-0002",
        ramo="Vehículos",
        cobertura="Pérdida Parcial",
        asegurado="M. Solís",
        asegurado_id="ASE-1002",
        poliza="POL-5002",
        ciudad="Quito",
        fecha_ocurrencia=date(2026, 4, 5),
        fecha_reporte=date(2026, 4, 14),
        monto_reclamado=9800.0,
        suma_asegurada=15000.0,
        estado="Pago Parcial",
        sucursal="Quito Norte",
        vehiculo=ClaimVehicle(marca="Kia", modelo="Rio", anio=2021, placa="PCM-5678"),
        proveedor="P-0042",
        descripcion="Daños por colisión en vía rápida, reportado nueve días después.",
        score=58,
        nivel=Tier.amarillo,
        alertas=[
            ClaimAlert(code="FS-01", puntos=8, severidad="med", detalle="Siniestro a 9 días del inicio de póliza."),
            ClaimAlert(code="FS-12", puntos=5, severidad="med", detalle="Reporte tardío (9 días desde la ocurrencia)."),
        ],
        timeline=[
            ClaimTimelineEvent(date="2026-04-05", title="Ocurrencia", tone="warn"),
            ClaimTimelineEvent(date="2026-04-14", title="Reporte", tone="warn", desc="9 días después"),
        ],
        documentos=[
            ClaimDocument(tipo="Denuncia", estado="Entregado"),
            ClaimDocument(tipo="Proforma", estado="Pendiente", falta=True),
        ],
        review=ClaimReview(status=ReviewStatus.pendiente),
    )


def claim_rojo() -> ClaimDetail:
    """High-risk — hard rule RF-01 (Total Loss for Theft) forces 🔴 regardless of score."""
    return ClaimDetail(
        id="SIN-0003",
        ramo="Vehículos",
        cobertura="Pérdida Total por Robo",
        asegurado="R. Castro",
        asegurado_id="ASE-1003",
        poliza="POL-5003",
        ciudad="Guayaquil",
        fecha_ocurrencia=date(2026, 5, 2),
        fecha_reporte=date(2026, 5, 7),
        monto_reclamado=28000.0,
        suma_asegurada=28000.0,
        estado="Reserva",
        sucursal="Guayaquil Centro",
        vehiculo=ClaimVehicle(marca="Toyota", modelo="Fortuner", anio=2023, placa="GSX-9012", chasis="9BR53ZEC4M0000000"),
        proveedor="P-0042",
        descripcion="Robo total del vehículo; denuncia presentada cinco días después.",
        score=88,
        nivel=Tier.rojo,
        alertas=[
            ClaimAlert(code="RF-01", puntos=0, severidad="high", detalle="Cobertura Pérdida Total por Robo (PTxRB)."),
            ClaimAlert(code="RF-06", puntos=0, severidad="high", detalle="Denuncia de robo atípica (>4 días)."),
            ClaimAlert(code="FS-14", puntos=5, severidad="med", detalle="Monto reclamado igual a la suma asegurada."),
        ],
        timeline=[
            ClaimTimelineEvent(date="2026-05-02", title="Ocurrencia", tone="danger"),
            ClaimTimelineEvent(date="2026-05-07", title="Denuncia", tone="danger", desc="5 días después"),
        ],
        documentos=[
            ClaimDocument(tipo="Denuncia policial", estado="Entregado"),
            ClaimDocument(tipo="Matrícula", estado="Pendiente", falta=True),
        ],
        review=ClaimReview(status=ReviewStatus.pendiente),
    )


ALL_FIXTURES: list[ClaimDetail] = [claim_verde(), claim_amarillo(), claim_rojo()]

FIXTURES_BY_TIER: dict[Tier, ClaimDetail] = {
    Tier.verde: claim_verde(),
    Tier.amarillo: claim_amarillo(),
    Tier.rojo: claim_rojo(),
}
