"""Offline VehicleDecoder backed by the deterministic synthetic codec.

For synthetic claims there is no real registry to call — the chassis was minted
by ``encode_synthetic_chassis`` and carries the (marca, modelo, año) triple. This
adapter reverses that against the SAME persisted vehicle vocabulary used at
encode time (cached read of ``data/config/vehicle_vocab.json``), so runtime
decode matches seed-time encode. It makes no network call, never raises, and
returns ``None`` for any chassis it cannot parse.
"""

from __future__ import annotations

from app.domain.vehicle_identity import (
    VehicleDecoder,
    VehicleSpec,
    decode_synthetic_chassis,
)


class RegistryVehicleDecoder(VehicleDecoder):
    """Decode a synthetic chassis locally via the deterministic codec."""

    async def decode(self, chassis: str) -> VehicleSpec | None:
        if not chassis:
            return None
        return decode_synthetic_chassis(chassis)
