"""Ecuadorian city-center coordinates (WGS84) + per-claim coord helpers.

Vehicle claims snap to simplified highway polylines inside each metro area.
Other ramos stay near the city center with a small inland-biased jitter.
"""

from __future__ import annotations

import hashlib

from app.core.ecuador_road_segments import (
    CITY_ROAD_POLYLINES,
    COASTAL_CITIES,
    GUAYAQUIL_ISLET_EXCLUDED_TAILS,
    GUAYAQUIL_ISLET_RELOCATION_ANCHOR,
    LatLng,
    Polyline,
)
from app.domain.ramos import normalize_ramo

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


def _interpolate_polyline(points: Polyline, t: float) -> LatLng:
    if len(points) == 1:
        return points[0]
    t_clamped = max(0.0, min(1.0, t))
    idx_f = t_clamped * (len(points) - 1)
    idx = int(idx_f)
    frac = idx_f - idx
    if idx >= len(points) - 1:
        return points[-1]
    lat_a, lng_a = points[idx]
    lat_b, lng_b = points[idx + 1]
    return (lat_a + (lat_b - lat_a) * frac, lng_a + (lng_b - lng_a) * frac)


def _segment_tangent(points: Polyline, t: float) -> tuple[float, float]:
    """Unit-ish direction of the polyline near ``t`` (lat/lng degrees)."""
    if len(points) < 2:
        return (1.0, 0.0)
    t_clamped = max(0.0, min(1.0, t))
    idx = min(int(t_clamped * (len(points) - 1)), len(points) - 2)
    dlat = points[idx + 1][0] - points[idx][0]
    dlng = points[idx + 1][1] - points[idx][1]
    length = (dlat * dlat + dlng * dlng) ** 0.5
    if length < 1e-9:
        return (1.0, 0.0)
    return (dlat / length, dlng / length)


def _apply_road_spread(
    point: LatLng,
    polyline: Polyline,
    position: float,
    claim_id: str,
) -> LatLng:
    """Nudge off the exact polyline so markers fill the metro, not a hairline."""
    lat, lng = point
    t_lat, t_lng = _segment_tangent(polyline, position)
    # Perpendicular in lat/lng space (swap + negate one component).
    n_lat, n_lng = -t_lng, t_lat
    perp = (_hash_unit(claim_id, 2) - 0.5) * 0.014
    along = (_hash_unit(claim_id, 3) - 0.5) * 0.010
    return (lat + t_lat * along + n_lat * perp, lng + t_lng * along + n_lng * perp)


def _claim_numeric_tail(claim_id: str) -> str:
    part = claim_id.rsplit("-", 1)[-1]
    return part.lstrip("0") or "0"


def _relocate_off_guayaquil_islet(claim_id: str, city: str, point: LatLng) -> LatLng:
    if city != "Guayaquil" or _claim_numeric_tail(claim_id) not in GUAYAQUIL_ISLET_EXCLUDED_TAILS:
        return point
    base_lat, base_lng = GUAYAQUIL_ISLET_RELOCATION_ANCHOR
    jitter_lat = (_hash_unit(claim_id, 4) - 0.5) * 0.006
    jitter_lng = (_hash_unit(claim_id, 5) - 0.5) * 0.006
    return (base_lat + jitter_lat, base_lng + jitter_lng)


def _coords_on_road(claim_id: str, city: str) -> LatLng | None:
    polylines = CITY_ROAD_POLYLINES.get(city)
    if not polylines:
        return None
    segment_idx = int(_hash_unit(claim_id, 0) * len(polylines)) % len(polylines)
    polyline = polylines[segment_idx]
    position = _hash_unit(claim_id, 1)
    base = _interpolate_polyline(polyline, position)
    spread = _apply_road_spread(base, polyline, position, claim_id)
    return _relocate_off_guayaquil_islet(claim_id, city, spread)


def _coords_near_city_center(claim_id: str, city: str) -> LatLng:
    lat_c, lng_c = ECUADOR_CITY_COORDS[city]
    lat = lat_c + (_hash_unit(claim_id, 1) - 0.5) * 0.04
    lng = lng_c + (_hash_unit(claim_id, 2) - 0.5) * 0.04
    if city in COASTAL_CITIES:
        lng = max(lng, lng_c - 0.015)
    return (lat, lng)


def coords_for_claim(
    claim_id: str,
    sucursal_or_city: str,
    *,
    ramo: str | None = None,
) -> tuple[float, float] | None:
    """Return (latitude, longitude) for a claim.

    Vehicle claims land on a deterministic point along a local highway polyline.
    Other ramos stay near the city center (clinics, homes, etc.).
    """
    city = normalize_to_city(sucursal_or_city)
    if city is None:
        return None

    canonical_ramo = normalize_ramo(ramo or "")
    if canonical_ramo == "vehiculos":
        on_road = _coords_on_road(claim_id, city)
        if on_road is not None:
            return on_road

    center = _coords_near_city_center(claim_id, city)
    return _relocate_off_guayaquil_islet(claim_id, city, center)
