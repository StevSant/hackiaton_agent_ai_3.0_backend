"""Port for the audit log store — append-only analyst + system activity.

Both ``DbAuditStore`` (production) and ``InMemoryAuditStore`` (no-DB / tests)
conform to this Protocol so the use cases and routes never depend on a concrete
implementation.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.audit import AuditEventOut


class AuditStore(Protocol):
    async def append(self, event: AuditEventOut) -> None: ...

    async def list_all(self) -> list[AuditEventOut]: ...

    async def list_recent(self, limit: int) -> list[AuditEventOut]: ...
