"""Female first-name pool — loaded from ``data/config/nombres_femeninos.json``."""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

NOMBRES_FEMENINOS: list[str] = load_pool("nombres_femeninos.json")
