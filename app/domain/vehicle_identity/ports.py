"""Port for chassis/VIN → VehicleSpec decoding.

Concrete adapters live under ``app/infrastructure/vehicle_decoder/`` and are
wired in ``app/api/deps.py::get_vehicle_decoder``. Use cases and tools depend on
this protocol, never on a concrete decoder (root CLAUDE.md §4 ports & adapters).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.vehicle_identity.models import VehicleSpec


@runtime_checkable
class VehicleDecoder(Protocol):
    """Decode a chassis/VIN into its canonical vehicle spec.

    Returns ``None`` when the chassis cannot be decoded (unparseable, registry
    miss, transport error). Implementations MUST never raise on a bad chassis —
    a failed decode is a ``None``, not an exception, so scoring never breaks.
    """

    async def decode(self, chassis: str) -> VehicleSpec | None:
        """Return the decoded spec, or None when the chassis is undecodable."""
        ...
