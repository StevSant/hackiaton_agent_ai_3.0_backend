"""Ciudad → sucursal mapping — loaded from ``data/config/sucursales.json``."""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

SUCURSALES: dict[str, str] = load_pool("sucursales.json")
