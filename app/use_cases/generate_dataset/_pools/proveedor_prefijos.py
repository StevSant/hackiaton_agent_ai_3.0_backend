"""Provider-name prefixes — loaded from ``data/config/proveedor_prefijos.json``."""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

PROVEEDOR_PREFIJOS: list[str] = load_pool("proveedor_prefijos.json")
