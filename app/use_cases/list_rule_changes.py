"""Use case: return the rule-change audit log (ordered most-recent first).

Reads from the rule-change store (DB-backed in production, in-memory in no-DB /
test mode). Entries are appended by ``update_rule_config`` as analysts pause
rules or retune thresholds from the dashboard; the store starts empty so the
page reflects real activity, never mock copy.
"""

from __future__ import annotations

from app.infrastructure.rule_changes import RuleChangesStore
from app.schemas.rule_changes import RuleChangeOut


async def list_rule_changes(
    store: RuleChangesStore,
    *,
    limit: int | None = None,
) -> list[RuleChangeOut]:
    if limit is not None:
        return await store.list_recent(limit)
    return await store.list_all()
