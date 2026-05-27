"""Default proveedor pool for vehicle claims — loaded from
``data/config/proveedores_default.json``.
"""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

PROVEEDORES_DEFAULT: list[str] = load_pool("proveedores_default.json")
