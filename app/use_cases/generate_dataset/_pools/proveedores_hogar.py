"""Default proveedor pool for hogar claims — loaded from
``data/config/proveedores_hogar.json``.
"""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

PROVEEDORES_HOGAR: list[str] = load_pool("proveedores_hogar.json")
