"""Process-singleton in-memory rule-change log.

Append-only history of edits to the rules catalog (pauses, threshold tweaks).
No-DB / test fallback for ``DbRuleChangesStore`` — state is lost on restart.
Async methods so it shares the ``RuleChangesStore`` Protocol with the DB store.
"""

from __future__ import annotations

from app.schemas.rule_changes import RuleChangeOut


class InMemoryRuleChangesStore:
    """Append-only rule-change log (process-local)."""

    def __init__(self) -> None:
        self._changes: list[RuleChangeOut] = []

    async def append(self, change: RuleChangeOut) -> None:
        self._changes.append(change)

    async def list_all(self) -> list[RuleChangeOut]:
        """Return all changes, most-recent first."""
        return sorted(self._changes, key=lambda c: c.ts, reverse=True)

    async def list_recent(self, limit: int) -> list[RuleChangeOut]:
        return (await self.list_all())[:limit]

    def clear(self) -> None:
        self._changes.clear()
