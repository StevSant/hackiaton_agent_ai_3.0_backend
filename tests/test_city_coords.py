"""Tests for deterministic claim coordinate placement."""

from __future__ import annotations

from app.core.city_coords import coords_for_claim, normalize_to_city
from app.core.ecuador_road_segments import COASTAL_CITIES


def test_normalize_to_city_from_sucursal() -> None:
    assert normalize_to_city("Quito Norte") == "Quito"
    assert normalize_to_city("Guayaquil Centro") == "Guayaquil"


def test_vehicle_claims_snap_to_roads_not_ocean() -> None:
    for city in COASTAL_CITIES:
        lat, lng = coords_for_claim(
            f"SIN-TEST-{city}",
            f"{city} Centro",
            ramo="Vehículos",
        )
        if city == "Esmeraldas":
            assert lng > -79.67, f"{city} landed in the ocean: {lng}"
        if city == "Machala":
            assert lng > -79.98, f"{city} landed in the ocean: {lng}"
        assert -5.0 < lat < 2.0
        assert -82.0 < lng < -75.0


def test_quito_vehicle_claims_spread_across_metro() -> None:
    longitudes: list[float] = []
    latitudes: list[float] = []
    for idx in range(40):
        lat, lng = coords_for_claim(f"SIN-QUITO-{idx:03d}", "Quito Norte", ramo="Vehículos")
        latitudes.append(lat)
        longitudes.append(lng)
    assert max(longitudes) - min(longitudes) > 0.08
    assert max(latitudes) - min(latitudes) > 0.08


def test_guayaquil_islet_exclusions_move_to_mainland() -> None:
    for claim_id in ("IMP-00141", "SIN-0052", "IMP-00235", "SIN-0073"):
        lat, lng = coords_for_claim(claim_id, "Guayaquil Centro", ramo="Vehículos")
        # Islet sits around lng ≈ -79.88 (east); mainland is further west.
        assert lng < -79.898, f"{claim_id} still on islet at {lng}"
        assert -2.19 < lat < -2.13


def test_non_vehicle_stays_near_city_center() -> None:
    lat, lng = coords_for_claim("SIN-SALUD-1", "Quito Norte", ramo="Salud")
    assert abs(lat - (-0.2202)) < 0.05
    assert abs(lng - (-78.5123)) < 0.05
