"""Port for the rule-overrides store — persisted per-rule runtime state.

Both ``DbRuleOverridesStore`` (production) and ``InMemoryRuleOverridesStore``
(no-DB / tests) conform to this Protocol so use cases never depend on a concrete
implementation.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.infrastructure.rule_overrides.record import RuleOverrideRecord


class RuleOverridesStore(Protocol):
    async def list_all(self) -> list[RuleOverrideRecord]: ...

    async def upsert(
        self,
        code: str,
        *,
        enabled: bool,
        thresholds: dict[str, Any],
        updated_by: str | None,
    ) -> RuleOverrideRecord: ...

    async def get(self, code: str) -> RuleOverrideRecord | None: ...
