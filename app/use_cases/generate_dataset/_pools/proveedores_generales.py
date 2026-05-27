"""Default proveedor pool for generales (commercial / cargo / electronics) claims —
loaded from ``data/config/proveedores_generales.json``.
"""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

PROVEEDORES_GENERALES: list[str] = load_pool("proveedores_generales.json")
