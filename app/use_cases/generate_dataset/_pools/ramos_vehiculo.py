"""Set of ramos that count as vehicle claims — loaded from
``data/config/ramos_vehiculo.json``.
"""

from __future__ import annotations

from app.use_cases.generate_dataset._pools._loader import load_pool

RAMOS_VEHICULO: frozenset[str] = frozenset(load_pool("ramos_vehiculo.json"))
