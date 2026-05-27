"""Process-singleton in-memory rule-change log.

Append-only history of edits to the rules catalog (weight changes, pauses,
threshold tweaks). Lives in memory for the hackathon — same shape and policy
as ``InMemoryAuditStore``.

No seed data: the log starts empty and only grows when an analista or
antifraude actually edits a rule via the (post-hackathon) PATCH endpoint.
Until that endpoint ships, the page renders an honest empty state.
"""

from __future__ import annotations

from app.schemas.rule_changes import RuleChangeOut


class InMemoryRuleChangesStore:
    """Append-only rule-change log."""

    def __init__(self) -> None:
        self._changes: list[RuleChangeOut] = []

    def append(self, change: RuleChangeOut) -> None:
        self._changes.append(change)

    def list_all(self) -> list[RuleChangeOut]:
        """Return all changes, most-recent first."""
        return sorted(self._changes, key=lambda c: c.ts, reverse=True)

    def list_recent(self, limit: int) -> list[RuleChangeOut]:
        return self.list_all()[:limit]

    def clear(self) -> None:
        self._changes.clear()
