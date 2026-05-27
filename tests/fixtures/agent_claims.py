"""Richer fixtures for the 12 NL questions test — 8 claims spanning proveedores,
ramos, ciudades, asegurados, with FS-01 for Q9 and missing docs for Q7.
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
from app.schemas.risk import FactorContribution, SimilarClaim, Tier


def _claim(
    *,
    id_: str,
    ramo: str,
    cobertura: str,
    asegurado: str,
    ciudad: str,
    monto: float,
    score: int,
    nivel: Tier,
    proveedor: str | None,
    alertas: list[ClaimAlert],
    documentos: list[ClaimDocument],
    ml_factors: list[FactorContribution] | None = None,
    similar: list[SimilarClaim] | None = None,
) -> ClaimDetail:
    return ClaimDetail(
        id=id_,
        ramo=ramo,
        cobertura=cobertura,
        asegurado=asegurado,
        asegurado_id=f"ASE-{id_.split('-')[-1]}",
        poliza=f"POL-{id_.split('-')[-1]}",
        ciudad=ciudad,
        fecha_ocurrencia=date(2026, 3, 1),
        fecha_reporte=date(2026, 3, 5),
        monto_reclamado=monto,
        suma_asegurada=max(monto * 1.2, 10000.0),
        estado="Reserva",
        sucursal=ciudad,
        vehiculo=ClaimVehicle(marca="Chevrolet", modelo="Sail", anio=2020, placa="ABC-0000"),
        proveedor=proveedor,
        descripcion=f"Caso sintético {id_} para pruebas del agente.",
        score=score,
        nivel=nivel,
        alertas=alertas,
        timeline=[ClaimTimelineEvent(date="2026-03-01", title="Ocurrencia", tone="warn")],
        documentos=documentos,
        review=ClaimReview(status=ReviewStatus.pendiente),
        ml_factors=ml_factors or [],
        similar=similar or [],
        anomaly_score=None,
    )


def agent_fixtures() -> list[ClaimDetail]:
    return [
        # rojo cluster — proveedor P-042 concentrates 3 alerts
        _claim(
            id_="SIN-1001",
            ramo="Vehículos",
            cobertura="Pérdida Total por Robo",
            asegurado="R. Castro",
            ciudad="Guayaquil",
            monto=28000.0,
            score=88,
            nivel=Tier.rojo,
            proveedor="P-042",
            alertas=[
                ClaimAlert(code="RF-01", puntos=0, severidad="high", detalle="PTxRB"),
                ClaimAlert(code="FS-07", puntos=10, severidad="high", detalle="Proveedor recurrente"),
            ],
            documentos=[
                ClaimDocument(tipo="Denuncia", estado="Entregado"),
                ClaimDocument(tipo="Matrícula", estado="Pendiente", falta=True),
            ],
            ml_factors=[
                FactorContribution(feature="monto_reclamado", shap_value=0.42, direction="up"),
                FactorContribution(feature="dias_entre_ocurrencia_reporte", shap_value=0.18, direction="up"),
                FactorContribution(feature="historial_siniestros_asegurado", shap_value=0.12, direction="up"),
            ],
            similar=[
                SimilarClaim(claim_id="SIN-1002", similarity=0.88, snippet="Robo total muy similar"),
            ],
        ),
        _claim(
            id_="SIN-1002",
            ramo="Vehículos",
            cobertura="Pérdida Total por Robo",
            asegurado="L. Vélez",
            ciudad="Guayaquil",
            monto=26000.0,
            score=82,
            nivel=Tier.rojo,
            proveedor="P-042",
            alertas=[
                ClaimAlert(code="RF-01", puntos=0, severidad="high", detalle="PTxRB"),
                ClaimAlert(code="FS-13", puntos=8, severidad="high", detalle="Narrativa muy similar"),
            ],
            documentos=[ClaimDocument(tipo="Denuncia", estado="Entregado")],
        ),
        _claim(
            id_="SIN-1003",
            ramo="Salud",
            cobertura="Hospitalización",
            asegurado="A. Pérez",
            ciudad="Quito",
            monto=12000.0,
            score=78,
            nivel=Tier.rojo,
            proveedor="P-042",
            alertas=[
                ClaimAlert(code="FS-11", puntos=10, severidad="high", detalle="Documentos inconsistentes"),
                ClaimAlert(code="FS-08", puntos=4, severidad="med", detalle="Docs incompletos"),
            ],
            documentos=[
                ClaimDocument(tipo="Historia clínica", estado="Pendiente", falta=True),
                ClaimDocument(tipo="Factura", estado="Pendiente", falta=True),
            ],
        ),
        # yellow band — FS-01 near policy boundary (powers Q9)
        _claim(
            id_="SIN-2001",
            ramo="Vehículos",
            cobertura="Choque",
            asegurado="M. Solís",
            ciudad="Cuenca",
            monto=4500.0,
            score=58,
            nivel=Tier.amarillo,
            proveedor="P-099",
            alertas=[
                ClaimAlert(code="FS-01", puntos=8, severidad="med", detalle="Cerca del inicio de póliza"),
                ClaimAlert(code="FS-12", puntos=5, severidad="med", detalle="Reporte tardío"),
            ],
            documentos=[ClaimDocument(tipo="Denuncia", estado="Entregado")],
        ),
        _claim(
            id_="SIN-2002",
            ramo="Vehículos",
            cobertura="Choque",
            asegurado="C. Ramírez",
            ciudad="Quito",
            monto=3200.0,
            score=52,
            nivel=Tier.amarillo,
            proveedor="P-099",
            alertas=[
                ClaimAlert(code="FS-01", puntos=8, severidad="med", detalle="Cerca del inicio de póliza"),
            ],
            documentos=[
                ClaimDocument(tipo="Proforma", estado="Pendiente", falta=True),
            ],
        ),
        _claim(
            id_="SIN-2003",
            ramo="Salud",
            cobertura="Ambulatorio",
            asegurado="A. Pérez",  # repeats — Q6
            ciudad="Quito",
            monto=900.0,
            score=44,
            nivel=Tier.amarillo,
            proveedor="P-077",
            alertas=[
                ClaimAlert(code="FS-03", puntos=8, severidad="med", detalle="Alta frecuencia"),
            ],
            documentos=[ClaimDocument(tipo="Factura", estado="Entregado")],
        ),
        # green band (control group)
        _claim(
            id_="SIN-3001",
            ramo="Vida",
            cobertura="Indemnización",
            asegurado="F. Mora",
            ciudad="Guayaquil",
            monto=1200.0,
            score=15,
            nivel=Tier.verde,
            proveedor=None,
            alertas=[],
            documentos=[ClaimDocument(tipo="Denuncia", estado="Entregado")],
        ),
        _claim(
            id_="SIN-3002",
            ramo="Generales",
            cobertura="Daños menores",
            asegurado="J. López",
            ciudad="Cuenca",
            monto=600.0,
            score=10,
            nivel=Tier.verde,
            proveedor=None,
            alertas=[],
            documentos=[ClaimDocument(tipo="Denuncia", estado="Entregado")],
        ),
    ]
