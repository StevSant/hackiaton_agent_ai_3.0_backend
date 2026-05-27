"""Config loader — reads config.yaml once and caches the result.

Rules read from `_cfg()` instead of hardcoding thresholds inline.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=1)
def _cfg() -> dict[str, Any]:
    """Load and cache config.yaml relative to this file's directory."""
    config_path = Path(__file__).parent / "config.yaml"
    with config_path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    return data


def rule_cfg(key: str) -> dict[str, Any]:
    """Return the sub-dict for a rule key, e.g. ``rule_cfg("FS_01")``."""
    cfg = _cfg()
    result: dict[str, Any] = cfg[key]
    return result


def tier_bands() -> dict[str, int]:
    """Return ``{verde_max, amarillo_max}`` from config."""
    cfg = _cfg()
    bands: dict[str, int] = cfg["tier_bands"]
    return bands
