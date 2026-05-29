"""Baseline runtime enable state for rules (pre-override default).

This is the single source of truth for which rules ship *disabled* before any
antifraude analyst toggles them. The runtime loader initialises its disabled-set
from here, and ``list_rules_config`` / lifespan hydration fall back to it when no
persisted override exists for a code.
"""

from __future__ import annotations

# FS-14 (amount near/above sum insured) is noisy on the synthetic dataset, so it
# ships paused until an antifraude analyst opts into it from the dashboard.
DEFAULT_DISABLED_CODES: frozenset[str] = frozenset({"FS-14"})
