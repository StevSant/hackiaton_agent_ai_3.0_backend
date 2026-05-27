"""Audit log API — THIN router.

Routes:
    GET /audit/events → list[AuditEventOut]   (any authenticated user)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_audit_store, get_current_user
from app.domain.auth.user import User
from app.infrastructure.audit import InMemoryAuditStore
from app.schemas.audit import AuditEventOut
from app.use_cases.list_audit_events import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventOut])
async def list_audit_events_route(
    store: Annotated[InMemoryAuditStore, Depends(get_audit_store)],
    limit: int | None = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[AuditEventOut]:
    return await list_audit_events(store, limit=limit)
