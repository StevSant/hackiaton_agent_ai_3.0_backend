"""Ramo (insurance branch) normalization.

The seed dataset has mixed casing/accents ("Vehículos" / "vehiculos") and
adjacent ramo names that we collapse into a small set of canonical categories
for triage UI: vehiculos / salud / vida / hogar / generales / otros.
"""

from __future__ import annotations

CANONICAL_RAMOS: tuple[str, ...] = (
    "vehiculos",
    "salud",
    "vida",
    "hogar",
    "generales",
    "otros",
)

_RAW_TO_CANONICAL: dict[str, str] = {
    "vehiculos": "vehiculos",
    "vehículos": "vehiculos",
    "transporte": "vehiculos",
    "auto": "vehiculos",
    "salud": "salud",
    "accidentes personales": "salud",
    "vida": "vida",
    "hogar": "hogar",
    "incendio": "hogar",
    "generales": "generales",
}


def _strip_accents(value: str) -> str:
    return (
        value.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .strip()
    )


def normalize_ramo(raw: str | None) -> str:
    """Map a raw ramo string to one of the CANONICAL_RAMOS keys."""
    if not raw:
        return "otros"
    key = raw.lower().strip()
    if key in _RAW_TO_CANONICAL:
        return _RAW_TO_CANONICAL[key]
    return _RAW_TO_CANONICAL.get(_strip_accents(raw), "otros")
