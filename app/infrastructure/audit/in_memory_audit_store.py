"""Process-singleton in-memory audit store.

Append-only log of analyst + system activity. Lives in memory for the
hackathon (no DB persistence yet); event objects are the same
``AuditEventOut`` Pydantic model the wire returns.

No seed data — the log starts empty and grows as real actions happen
(escalations, take, dictamen, close). This matches the project's no-fallback
rule: the audit page reflects real activity, never mock copy.
"""

from __future__ import annotations

from app.schemas.audit import AuditEventOut


class InMemoryAuditStore:
    """Append-only audit log, keyed implicitly by insertion order."""

    def __init__(self) -> None:
        self._events: list[AuditEventOut] = []

    async def append(self, event: AuditEventOut) -> None:
        """Append one event to the log."""
        self._events.append(event)

    async def list_all(self) -> list[AuditEventOut]:
        """Return all events, most-recent first."""
        return sorted(self._events, key=lambda e: e.ts, reverse=True)

    async def list_recent(self, limit: int) -> list[AuditEventOut]:
        """Return up to *limit* most-recent events."""
        return (await self.list_all())[:limit]

    def clear(self) -> None:
        """Drop every event — only used by tests."""
        self._events.clear()
