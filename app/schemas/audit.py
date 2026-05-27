"""Wire schema for GET /audit/events — analyst + system activity log."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AuditActor(str, Enum):
    analista = "analista"
    agente = "agente"
    sistema = "sistema"


class AuditAction(str, Enum):
    apertura = "apertura"
    escalamiento = "escalamiento"
    consulta_ia = "consulta_ia"
    cambio_regla = "cambio_regla"
    cierre = "cierre"
    export = "export"


class AuditEventOut(BaseModel):
    id: str
    ts: datetime
    actor: AuditActor
    actor_name: str
    action: AuditAction
    title: str
    detail: str
    target: str | None = None
