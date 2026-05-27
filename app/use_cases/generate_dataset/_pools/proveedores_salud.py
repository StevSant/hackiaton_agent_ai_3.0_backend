"""Default proveedor pool for salud claims — loaded from
``data/config/proveedores_salud.json``.
"""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

PROVEEDORES_SALUD: list[str] = load_pool("proveedores_salud.json")
