"""Provider-name qualifiers — loaded from ``data/config/proveedor_qualifiers.json``."""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

PROVEEDOR_QUALIFIERS: list[str] = load_pool("proveedor_qualifiers.json")
