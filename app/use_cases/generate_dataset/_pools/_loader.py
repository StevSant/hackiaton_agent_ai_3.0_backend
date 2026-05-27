"""Thin JSON loader for synthetic-generator seed pools.

Each pool lives at ``data/config/<name>.json`` as either::

    {"_comment": "...", "items": [...]}        # list-shaped pool
    {"_comment": "...", "mapping": {...}}      # dict-shaped pool

Edit the JSON file to change a pool — do not hardcode pool values in Python.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).resolve().parents[4] / "data" / "config"


def load_pool(filename: str) -> Any:
    """Return the ``items`` list or ``mapping`` dict from a pool JSON."""
    path = _CONFIG_DIR / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "items" in payload:
        return payload["items"]
    if "mapping" in payload:
        return payload["mapping"]
    raise RuntimeError(
        f"Malformed pool seed at {path}: missing 'items' or 'mapping' key"
    )
