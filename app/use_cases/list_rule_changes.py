"""Use case: return the rule-change audit log (ordered most-recent first)."""

from __future__ import annotations

from app.schemas.rule_changes import RuleChangeOut
from app.use_cases._seeds.rule_changes_seed import RULE_CHANGES


async def list_rule_changes(*, limit: int | None = None) -> list[RuleChangeOut]:
    changes = sorted(RULE_CHANGES, key=lambda c: c.ts, reverse=True)
    if limit is not None:
        changes = changes[:limit]
    return changes
