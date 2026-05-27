"""Male first-name pool — loaded from ``data/config/nombres_masculinos.json``."""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

NOMBRES_MASCULINOS: list[str] = load_pool("nombres_masculinos.json")
