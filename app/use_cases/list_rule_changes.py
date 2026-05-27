"""Use case: return the rule-change audit log (ordered most-recent first).

Reads from the in-memory rule-change store. Edits are appended as analysts
modify rule weights / thresholds / status via the (future) PATCH endpoint;
the store starts empty so the page reflects real activity, never mock copy.
"""

from __future__ import annotations

from app.infrastructure.rule_changes import InMemoryRuleChangesStore
from app.schemas.rule_changes import RuleChangeOut


async def list_rule_changes(
    store: InMemoryRuleChangesStore,
    *,
    limit: int | None = None,
) -> list[RuleChangeOut]:
    if limit is not None:
        return store.list_recent(limit)
    return store.list_all()
