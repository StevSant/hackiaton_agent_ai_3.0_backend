"""Hybrid VehicleDecoder — route real VINs to NHTSA, synthetic chassis to registry.

The dataset mixes two chassis shapes: deterministic synthetic chassis minted by
``encode_synthetic_chassis`` (carry the marker prefix/suffix) and real 17-char
VINs. This router inspects the chassis and dispatches:

- synthetic-shaped         → ``RegistryVehicleDecoder`` (offline, reverses the codec)
- real-VIN-shaped          → ``NhtsaVehicleDecoder``     (live vPIC lookup)
- anything else            → registry (offline best-effort), then None

A real VIN is 17 alphanumeric chars excluding I/O/Q, and is NOT one of our
synthetic-encoded chassis (the synthetic marker takes precedence so a minted
chassis is never sent to the network).
"""

from __future__ import annotations

from app.domain.vehicle_identity import (
    SYNTHETIC_LENGTH,
    VehicleDecoder,
    VehicleSpec,
    is_synthetic_chassis,
)

# Real VINs use the 17-char alphabet minus I, O, Q (ISO 3779).
_VIN_ALPHABET = frozenset("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")


def _looks_like_real_vin(chassis: str) -> bool:
    """True when *chassis* has the structural shape of a real-world VIN."""
    if len(chassis) != SYNTHETIC_LENGTH:  # real VINs are also 17 chars
        return False
    return all(ch in _VIN_ALPHABET for ch in chassis.upper())


class HybridVehicleDecoder(VehicleDecoder):
    """Dispatch chassis decoding between the offline registry and live NHTSA."""

    def __init__(
        self,
        registry: VehicleDecoder,
        nhtsa: VehicleDecoder,
    ) -> None:
        self._registry = registry
        self._nhtsa = nhtsa

    async def decode(self, chassis: str) -> VehicleSpec | None:
        if not chassis:
            return None
        # Synthetic marker always wins so minted chassis never hit the network.
        if is_synthetic_chassis(chassis):
            return await self._registry.decode(chassis)
        if _looks_like_real_vin(chassis):
            return await self._nhtsa.decode(chassis)
        # Unknown shape — try the offline reverse as a best-effort, else None.
        return await self._registry.decode(chassis)
