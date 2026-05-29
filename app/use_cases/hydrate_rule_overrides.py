"""hydrate_rule_overrides — push persisted rule overrides into the engine loader.

Reads every ``rule_overrides`` row and translates them into the two primitives
the domain loader understands: the set of paused rule codes and the per-rule
threshold overlay. Called at lifespan startup and after every PATCH so the
running engine always reflects the persisted state.

Default-disabled rules (``DEFAULT_DISABLED_CODES``) stay paused unless an explicit
override row re-enables them.
"""

from __future__ import annotations

from app.domain.rules.defaults import DEFAULT_DISABLED_CODES
from app.domain.rules.loader import apply_overrides
from app.infrastructure.rule_overrides import RuleOverridesStore


def _config_key(code: str) -> str:
    """Map a rule code (``FS-01``) to its config.yaml key (``FS_01``)."""
    return code.replace("-", "_")


async def hydrate_rule_overrides(store: RuleOverridesStore) -> None:
    records = await store.list_all()
    by_code = {r.code: r for r in records}

    disabled: set[str] = set()
    # Baseline: shipped-disabled rules stay paused unless explicitly re-enabled.
    for code in DEFAULT_DISABLED_CODES:
        record = by_code.get(code)
        if record is None or not record.enabled:
            disabled.add(code)

    threshold_overrides: dict[str, dict[str, float]] = {}
    for record in records:
        if not record.enabled:
            disabled.add(record.code)
        if record.thresholds:
            threshold_overrides[_config_key(record.code)] = dict(record.thresholds)

    apply_overrides(disabled, threshold_overrides)
