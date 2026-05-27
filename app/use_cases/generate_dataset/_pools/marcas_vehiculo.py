"""Vehicle-brand pool — loaded from ``data/config/marcas_vehiculo.json``."""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

MARCAS_VEHICULO: list[str] = load_pool("marcas_vehiculo.json")
