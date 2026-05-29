"""In-memory rule-overrides store — no-DB / test fallback.

Same contract as ``DbRuleOverridesStore`` but process-local; state is lost on
restart. Used only when no session factory is registered.
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.rule_overrides.record import RuleOverrideRecord


class InMemoryRuleOverridesStore:
    def __init__(self) -> None:
        self._by_code: dict[str, RuleOverrideRecord] = {}

    async def list_all(self) -> list[RuleOverrideRecord]:
        return list(self._by_code.values())

    async def get(self, code: str) -> RuleOverrideRecord | None:
        return self._by_code.get(code)

    async def upsert(
        self,
        code: str,
        *,
        enabled: bool,
        thresholds: dict[str, Any],
        updated_by: str | None,
    ) -> RuleOverrideRecord:
        record = RuleOverrideRecord(
            code=code, enabled=enabled, thresholds=dict(thresholds)
        )
        self._by_code[code] = record
        return record
