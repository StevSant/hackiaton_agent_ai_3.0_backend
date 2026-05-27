"""Static seed for GET /audit/events.

The audit log is not yet persisted (see use_cases/_seeds/__init__.py).
Demo data mirrors the analyst's working day on 2026-05-26.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.audit import AuditAction, AuditActor, AuditEventOut


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


AUDIT_EVENTS: list[AuditEventOut] = [
    AuditEventOut(
        id="ev_001",
        ts=_ts("2026-05-26T14:42:00"),
        actor=AuditActor.analista,
        actor_name="Lucía Vélez",
        action=AuditAction.escalamiento,
        title="Escaló SIN-2026-08412 a Unidad Antifraude",
        detail="Score 91/100 · 5 señales activadas (RF-01, RF-03, RF-06, RF-05, AF-02).",
        target="SIN-2026-08412",
    ),
    AuditEventOut(
        id="ev_002",
        ts=_ts("2026-05-26T14:38:00"),
        actor=AuditActor.agente,
        actor_name="Centinela IA",
        action=AuditAction.consulta_ia,
        title='Respondió "¿Por qué este caso es alto riesgo?"',
        detail="Citó SIN-2026-08412 y la regla RF-01. Tiempo de respuesta: 1.4s.",
        target="SIN-2026-08412",
    ),
    AuditEventOut(
        id="ev_003",
        ts=_ts("2026-05-26T14:31:00"),
        actor=AuditActor.analista,
        actor_name="Lucía Vélez",
        action=AuditAction.apertura,
        title="Abrió detalle del caso",
        detail="Revisión inicial · 0 acciones tomadas aún.",
        target="SIN-2026-08412",
    ),
    AuditEventOut(
        id="ev_004",
        ts=_ts("2026-05-26T13:55:00"),
        actor=AuditActor.sistema,
        actor_name="Ingestor",
        action=AuditAction.apertura,
        title="Nuevo siniestro ingresado",
        detail="SIN-2026-08412 ingresó vía batch nocturno · score calculado: 91.",
        target="SIN-2026-08412",
    ),
    AuditEventOut(
        id="ev_005",
        ts=_ts("2026-05-26T13:42:00"),
        actor=AuditActor.analista,
        actor_name="Lucía Vélez",
        action=AuditAction.cierre,
        title="Cerró SIN-2026-08376 sin observación",
        detail="Score 12/100 · documentación completa, sin patrones atípicos.",
        target="SIN-2026-08376",
    ),
    AuditEventOut(
        id="ev_006",
        ts=_ts("2026-05-26T12:18:00"),
        actor=AuditActor.agente,
        actor_name="Centinela IA",
        action=AuditAction.consulta_ia,
        title='Respondió "Top 10 siniestros con mayor riesgo"',
        detail="Generó lista priorizada con score y reglas activadas. Tiempo: 2.1s.",
    ),
    AuditEventOut(
        id="ev_007",
        ts=_ts("2026-05-26T11:54:00"),
        actor=AuditActor.analista,
        actor_name="Lucía Vélez",
        action=AuditAction.escalamiento,
        title="Escaló SIN-2026-08354 a Unidad Antifraude",
        detail="Robo a 9 días del inicio de vigencia · monto 96% suma asegurada.",
        target="SIN-2026-08354",
    ),
    AuditEventOut(
        id="ev_008",
        ts=_ts("2026-05-26T10:32:00"),
        actor=AuditActor.sistema,
        actor_name="Motor de reglas",
        action=AuditAction.cambio_regla,
        title="Recalibración automática de umbral FS-13",
        detail="Umbral subió de 0.82 a 0.85 según retroalimentación de la semana.",
    ),
    AuditEventOut(
        id="ev_009",
        ts=_ts("2026-05-26T10:11:00"),
        actor=AuditActor.analista,
        actor_name="Lucía Vélez",
        action=AuditAction.export,
        title="Exportó bandeja a CSV",
        detail="14 casos · filtro: tier rojo + amarillo.",
    ),
    AuditEventOut(
        id="ev_010",
        ts=_ts("2026-05-26T09:48:00"),
        actor=AuditActor.agente,
        actor_name="Centinela IA",
        action=AuditAction.consulta_ia,
        title='Respondió "¿Qué proveedores concentran alertas?"',
        detail="Identificó PRV-0142 (Auto-Élite) con 9 alertas en 14 casos.",
        target="PRV-0142",
    ),
    AuditEventOut(
        id="ev_011",
        ts=_ts("2026-05-26T09:24:00"),
        actor=AuditActor.analista,
        actor_name="Lucía Vélez",
        action=AuditAction.apertura,
        title="Abrió detalle del caso",
        detail="Revisión inicial de caso atípico.",
        target="SIN-2026-08398",
    ),
    AuditEventOut(
        id="ev_012",
        ts=_ts("2026-05-25T17:02:00"),
        actor=AuditActor.sistema,
        actor_name="Motor de reglas",
        action=AuditAction.cambio_regla,
        title="Regla FS-14 pausada por la analista",
        detail="FS-14 (monto cerca de suma asegurada) marcada como observada solamente.",
    ),
]
