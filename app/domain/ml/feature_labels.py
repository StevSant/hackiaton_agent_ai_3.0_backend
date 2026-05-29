"""Spanish business labels for every ML feature in ``FEATURE_NAMES``.

The panel specialists (and any user-facing surface fed by the backend) must
never expose raw feature identifiers like ``es_robo`` — analysts read business
language. Mirrors the frontend map in ``features/claims/utils/feature-labels.ts``;
keep both in lockstep when a feature is added.
"""

from __future__ import annotations

FEATURE_LABELS: dict[str, str] = {
    "monto_reclamado": "Monto reclamado",
    "suma_asegurada": "Suma asegurada",
    "monto_vs_suma_pct": "Monto vs. suma asegurada (%)",
    "monto_vs_reparacion_avg_pct": "Monto vs. promedio de reparación (%)",
    "dias_entre_ocurrencia_reporte": "Días entre ocurrencia y reporte",
    "dias_desde_inicio_poliza": "Días desde inicio de póliza",
    "dias_desde_fin_poliza": "Días desde fin de póliza",
    "demora_denuncia_horas": "Demora de la denuncia (horas)",
    "historial_siniestros_asegurado": "Historial de siniestros del asegurado",
    "frecuencia_vehiculo": "Frecuencia de reclamos del vehículo",
    "frecuencia_conductor": "Frecuencia de reclamos del conductor",
    "eventos_rc_previos": "Eventos RC previos",
    "proveedor_casos_observados": "Casos observados del proveedor",
    "narrativa_similar_score": "Similitud narrativa",
    "documentos_incompletos": "Documentos incompletos",
    "inconsistencia_documental": "Inconsistencia documental",
    "narrativa_clonada": "Narrativa clonada",
    "evento_medianoche": "Evento de medianoche",
    "es_robo": "Cobertura de robo",
    "cobertura_rc": "Cobertura RC",
    "proveedor_en_lista_restrictiva": "Proveedor en lista restrictiva",
    "beneficiario_en_lista_restrictiva": "Beneficiario en lista restrictiva",
    "narrativa_ilogica": "Narrativa ilógica",
}


def feature_label(name: str) -> str:
    """Business label for a feature; falls back to the raw name if unknown."""
    return FEATURE_LABELS.get(name, name)
