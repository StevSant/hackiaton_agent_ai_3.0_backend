"""Ecuadorian city-center coordinates (WGS84) + per-claim coord helpers.

Used by:
- the synthetic dataset generator (to emit deterministic per-claim lat/lng)
- the Alembic backfill migration that populates existing rows
- any future place that needs to resolve a sucursal/ciudad to a point on the map

Coordinates from OpenStreetMap city centers, rounded to ~4 decimal places.
"""

from __future__ import annotations

import hashlib

# Bare city name → (latitude, longitude).
ECUADOR_CITY_COORDS: dict[str, tuple[float, float]] = {
    "Quito": (-0.2202, -78.5123),
    "Guayaquil": (-2.1710, -79.9224),
    "Cuenca": (-2.9001, -79.0059),
    "Santo Domingo": (-0.2522, -79.1754),
    "Manta": (-0.9677, -80.7089),
    "Ambato": (-1.2528, -78.6155),
    "Portoviejo": (-1.0541, -80.4521),
    "Machala": (-3.2581, -79.9605),
    "Loja": (-3.9931, -79.2042),
    "Riobamba": (-1.6727, -78.6492),
    "Ibarra": (0.3601, -78.1361),
    "Esmeraldas": (0.9683, -79.6517),
    "Babahoyo": (-1.8021, -79.5343),
    "Quevedo": (-1.0210, -79.4632),
    "Latacunga": (-0.9341, -78.6151),
    "Tulcán": (0.8167, -77.7167),
    "Milagro": (-2.1349, -79.5872),
}


def normalize_to_city(sucursal_or_city: str) -> str | None:
    """Map a sucursal name (e.g. 'Quito Norte') to its base city ('Quito')."""
    if not sucursal_or_city:
        return None
    if sucursal_or_city in ECUADOR_CITY_COORDS:
        return sucursal_or_city
    for city in ECUADOR_CITY_COORDS:
        if city in sucursal_or_city:
            return city
    return None


def _hash_unit(seed: str, salt: int) -> float:
    """Deterministic float in [0, 1) from (seed, salt)."""
    h = hashlib.md5(f"{seed}-{salt}".encode()).hexdigest()  # noqa: S324
    return (int(h[:8], 16) % 10_000) / 10_000


def coords_for_claim(claim_id: str, sucursal_or_city: str) -> tuple[float, float] | None:
    """Return (latitude, longitude) for a claim: city center + ±~0.05° (≈5 km) jitter.

    The jitter is derived from ``claim_id`` so a given claim always lands on
    the same spot. Returns ``None`` when the sucursal is not in the lookup.
    """
    city = normalize_to_city(sucursal_or_city)
    if city is None:
        return None
    lat_c, lng_c = ECUADOR_CITY_COORDS[city]
    lat = lat_c + (_hash_unit(claim_id, 1) - 0.5) * 0.10
    lng = lng_c + (_hash_unit(claim_id, 2) - 0.5) * 0.10
    return (lat, lng)
