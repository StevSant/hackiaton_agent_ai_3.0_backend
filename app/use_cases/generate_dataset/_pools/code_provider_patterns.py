"""Prefixes that mark a 'proveedor' value as an internal code, not a display
name — loaded from ``data/config/code_provider_patterns.json``.
"""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

CODE_PROVIDER_PATTERNS: tuple[str, ...] = tuple(load_pool("code_provider_patterns.json"))
