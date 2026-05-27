"""Surname pool — loaded from ``data/config/apellidos.json``."""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

APELLIDOS: list[str] = load_pool("apellidos.json")
