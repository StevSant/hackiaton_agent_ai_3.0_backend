"""Config loader — reads config.yaml once and caches the result.

Rules read from `rule_cfg()` instead of hardcoding thresholds inline.

Runtime overrides
-----------------
Antifraude analysts can pause rules or retune their thresholds from the
dashboard. Those edits are persisted in the DB and pushed into this module via
``apply_overrides`` (at lifespan startup and after every PATCH). The domain stays
DB-free: infrastructure translates persisted rows into plain primitives and calls
``apply_overrides`` — the rules just read the merged values through ``rule_cfg``
and ``rule_enabled``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.domain.rules.defaults import DEFAULT_DISABLED_CODES

# Runtime override state (hydrated from the DB by infrastructure). Threshold
# overrides are keyed by *config key* (e.g. "FS_01", not "FS-01").
_DISABLED_CODES: set[str] = set(DEFAULT_DISABLED_CODES)
_THRESHOLD_OVERRIDES: dict[str, dict[str, Any]] = {}


@lru_cache(maxsize=1)
def _cfg() -> dict[str, Any]:
    """Load and cache config.yaml relative to this file's directory."""
    config_path = Path(__file__).parent / "config.yaml"
    with config_path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    return data


def rule_cfg(key: str) -> dict[str, Any]:
    """Return the sub-dict for a rule key, e.g. ``rule_cfg("FS_01")``.

    Persisted threshold overrides for the key are merged on top of the YAML
    defaults so a dashboard edit takes effect on the next evaluation.
    """
    base: dict[str, Any] = _cfg()[key]
    override = _THRESHOLD_OVERRIDES.get(key)
    if override:
        return {**base, **override}
    return base


def tier_bands() -> dict[str, int]:
    """Return ``{verde_max, amarillo_max}`` from config."""
    cfg = _cfg()
    bands: dict[str, int] = cfg["tier_bands"]
    return bands


def numeric_thresholds(key: str) -> dict[str, float]:
    """Return a rule's *effective* numeric thresholds (defaults ⊕ overrides).

    Only scalar int/float entries are returned (bool and list entries — e.g.
    RF-01's coverage list — are excluded), so this is the editable surface the
    dashboard threshold editor renders. Returns ``{}`` for rules with no config
    block (e.g. RF-02..04, which are pure hard rules).
    """
    cfg = _cfg()
    if key not in cfg:
        return {}
    return {
        k: float(v)
        for k, v in rule_cfg(key).items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def apply_overrides(
    disabled: set[str], threshold_overrides: dict[str, dict[str, Any]]
) -> None:
    """Replace the runtime override state (called by infra after a DB read).

    Args:
        disabled:            Rule codes (``FS-01`` form) that are currently paused.
        threshold_overrides: Per-rule threshold overrides keyed by *config key*
                             (``FS_01`` form) → ``{threshold_name: value}``.
    """
    global _DISABLED_CODES
    _DISABLED_CODES = set(disabled)
    _THRESHOLD_OVERRIDES.clear()
    _THRESHOLD_OVERRIDES.update(threshold_overrides)


def reset_overrides() -> None:
    """Restore the shipped defaults (used by tests for isolation)."""
    global _DISABLED_CODES
    _DISABLED_CODES = set(DEFAULT_DISABLED_CODES)
    _THRESHOLD_OVERRIDES.clear()


def rule_enabled(code: str) -> bool:
    """Return whether a rule (``FS-01`` form) is active in the engine."""
    return code not in _DISABLED_CODES


def disabled_codes() -> set[str]:
    """Return a copy of the currently-paused rule codes (``FS-01`` form)."""
    return set(_DISABLED_CODES)
