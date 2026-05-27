"""Ramo (insurance branch) normalization + display-label lookup.

The seed dataset has mixed casing/accents ("Vehículos" / "vehiculos") and
adjacent ramo names that we collapse into a small set of canonical categories
for triage UI: vehiculos / salud / vida / hogar / generales / otros.

Display labels (Spanish text shown in the donut / aggregation cards) live in
``data/config/ramo_labels.json`` so they can be edited without touching code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

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
    "auto": "vehiculos",
    "salud": "salud",
    "accidentes personales": "salud",
    "vida": "vida",
    "hogar": "hogar",
    "incendio": "hogar",
    "generales": "generales",
    # Commercial / cargo / equipment lines roll up under "generales" for the
    # triage donut — they share the same operational queue and provider pool.
    "transporte": "generales",
    "mercancias en transito": "generales",
    "mercancías en tránsito": "generales",
    "equipo electronico": "generales",
    "equipo electrónico": "generales",
    "fianzas": "generales",
    "responsabilidad civil comercial": "generales",
}

_RAMO_LABELS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "config" / "ramo_labels.json"
)


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


@lru_cache(maxsize=1)
def load_ramo_labels() -> dict[str, str]:
    """Load `{canonical_ramo: display_label}` from the seed file.

    Cached for the process lifetime so the JSON is parsed once. The file is
    the single source of truth — edit ``data/config/ramo_labels.json``, not
    Python code, to retitle a donut slice.
    """
    payload = json.loads(_RAMO_LABELS_PATH.read_text(encoding="utf-8"))
    labels = payload.get("labels")
    if not isinstance(labels, dict):
        raise RuntimeError(
            f"Malformed ramo labels seed at {_RAMO_LABELS_PATH}: missing 'labels' object"
        )
    return {str(k): str(v) for k, v in labels.items()}


def label_for(canonical_ramo: str) -> str:
    """Return the display label for a canonical ramo, or the canonical key if unmapped."""
    return load_ramo_labels().get(canonical_ramo, canonical_ramo)
