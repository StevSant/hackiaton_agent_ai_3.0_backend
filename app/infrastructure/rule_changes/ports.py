"""Port for the rule-change log store — append-only history of rule edits.

Both ``DbRuleChangesStore`` (production) and ``InMemoryRuleChangesStore``
(no-DB / tests) conform to this Protocol.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.rule_changes import RuleChangeOut


class RuleChangesStore(Protocol):
    async def append(self, change: RuleChangeOut) -> None: ...

    async def list_all(self) -> list[RuleChangeOut]: ...

    async def list_recent(self, limit: int) -> list[RuleChangeOut]: ...
