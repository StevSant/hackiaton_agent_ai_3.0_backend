"""Vehicle-model pool — loaded from ``data/config/modelos_vehiculo.json``."""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

MODELOS_VEHICULO: list[str] = load_pool("modelos_vehiculo.json")
