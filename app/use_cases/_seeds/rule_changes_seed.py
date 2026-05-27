"""Static seed for GET /rules/changes — audit log of rule-config edits."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.rule_changes import RuleChangeKind, RuleChangeOut


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


RULE_CHANGES: list[RuleChangeOut] = [
    RuleChangeOut(
        id="rc_010",
        ts=_ts("2026-05-26T10:32:00"),
        actor="Motor de reglas",
        rule_code="FS-13",
        rule_name="Narrativas similares (NLP)",
        kind=RuleChangeKind.umbral,
        summary="Recalibración automática del umbral de similitud.",
        before_value="0.82",
        after_value="0.85",
    ),
    RuleChangeOut(
        id="rc_009",
        ts=_ts("2026-05-25T17:02:00"),
        actor="Lucía Vélez",
        rule_code="FS-14",
        rule_name="Monto cerca de suma asegurada",
        kind=RuleChangeKind.pausada,
        summary="Marcada como observada — generaba muchos falsos positivos en pólizas pequeñas.",
    ),
    RuleChangeOut(
        id="rc_008",
        ts=_ts("2026-05-24T09:15:00"),
        actor="Lucía Vélez",
        rule_code="RF-06",
        rule_name="Demora atípica en denuncia",
        kind=RuleChangeKind.editada,
        summary="Cambió el umbral mínimo de demora aceptable.",
        before_value="> 4 días",
        after_value="> 3 días",
    ),
    RuleChangeOut(
        id="rc_007",
        ts=_ts("2026-05-22T14:48:00"),
        actor="Pablo Reyes",
        rule_code="FS-07",
        rule_name="Beneficiario / proveedor recurrente",
        kind=RuleChangeKind.editada,
        summary="Aumentó el peso máximo de la regla.",
        before_value="8 pts",
        after_value="10 pts",
    ),
    RuleChangeOut(
        id="rc_006",
        ts=_ts("2026-05-20T11:22:00"),
        actor="Pablo Reyes",
        rule_code="RF-07",
        rule_name="Narrativa similar (>85%)",
        kind=RuleChangeKind.reactivada,
        summary="Reactivada después del ajuste del modelo de embeddings.",
    ),
    RuleChangeOut(
        id="rc_005",
        ts=_ts("2026-05-18T16:04:00"),
        actor="Lucía Vélez",
        rule_code="FS-11",
        rule_name="Documentos inconsistentes",
        kind=RuleChangeKind.editada,
        summary="Reclasificada como crítica por incidente de mayo.",
        before_value="amarillo",
        after_value="rojo",
    ),
    RuleChangeOut(
        id="rc_004",
        ts=_ts("2026-05-15T08:30:00"),
        actor="Sistema",
        rule_code="RF-03",
        rule_name="Coincidencia con lista restrictiva",
        kind=RuleChangeKind.umbral,
        summary="Lista restrictiva sincronizada con nueva fuente APS.",
        before_value="1240 entradas",
        after_value="1316 entradas",
    ),
    RuleChangeOut(
        id="rc_003",
        ts=_ts("2026-05-12T13:18:00"),
        actor="Pablo Reyes",
        rule_code="FS-12",
        rule_name="Reporte tardío",
        kind=RuleChangeKind.creada,
        summary="Regla nueva derivada del patrón observado en bandeja de abril.",
    ),
    RuleChangeOut(
        id="rc_002",
        ts=_ts("2026-05-09T17:55:00"),
        actor="Lucía Vélez",
        rule_code="AF-05",
        rule_name="Sin tercero identificado",
        kind=RuleChangeKind.pausada,
        summary="Pausada temporalmente mientras se validan datos del módulo de testigos.",
    ),
    RuleChangeOut(
        id="rc_001",
        ts=_ts("2026-05-05T09:00:00"),
        actor="Sistema",
        rule_code="RF-01..RF-04",
        rule_name="Reglas críticas iniciales",
        kind=RuleChangeKind.creada,
        summary="Importación inicial del catálogo desde la especificación del reto.",
    ),
]
