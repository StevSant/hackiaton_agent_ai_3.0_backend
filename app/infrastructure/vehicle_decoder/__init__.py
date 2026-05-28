"""Vehicle-decoder adapters behind the ``VehicleDecoder`` port.

- ``RegistryVehicleDecoder`` — offline, reverses the synthetic chassis codec.
- ``NhtsaVehicleDecoder``     — live NHTSA vPIC lookup for real VINs.
- ``HybridVehicleDecoder``    — routes by chassis shape (synthetic → registry,
                                real VIN → NHTSA).

Re-exported at package level so callers import from the package, not the files.
"""

from app.infrastructure.vehicle_decoder.hybrid_adapter import HybridVehicleDecoder
from app.infrastructure.vehicle_decoder.nhtsa_adapter import (
    NhtsaVehicleDecoder,
    build_nhtsa_vehicle_decoder,
)
from app.infrastructure.vehicle_decoder.registry_adapter import RegistryVehicleDecoder

__all__ = [
    "HybridVehicleDecoder",
    "NhtsaVehicleDecoder",
    "RegistryVehicleDecoder",
    "build_nhtsa_vehicle_decoder",
]
