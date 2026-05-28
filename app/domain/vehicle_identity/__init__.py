"""Vehicle-identity domain: decode a chassis/VIN to a canonical spec and compare
it against the vehicle declared on a claim. A contradiction is a fraud signal.

Public surface re-exported here so consumers import from the package, not the
implementation files (code-style: package-level re-exports).
"""

from app.domain.vehicle_identity.models import VehicleMatchResult, VehicleSpec
from app.domain.vehicle_identity.ports import VehicleDecoder
from app.domain.vehicle_identity.synthetic_codec import (
    SYNTHETIC_LENGTH,
    SYNTHETIC_PREFIX,
    SYNTHETIC_SUFFIX,
    decode_synthetic_chassis,
    encode_synthetic_chassis,
    is_synthetic_chassis,
)
from app.domain.vehicle_identity.vehicle_vocab import (
    VEHICLE_VOCAB_PATH,
    build_vehicle_vocab,
    load_vehicle_vocab,
)
from app.domain.vehicle_identity.verifier import ANIO_TOLERANCE, compare_vehicle
from app.domain.vehicle_identity.vocab_entry import VehicleVocab

__all__ = [
    "ANIO_TOLERANCE",
    "SYNTHETIC_LENGTH",
    "SYNTHETIC_PREFIX",
    "SYNTHETIC_SUFFIX",
    "VEHICLE_VOCAB_PATH",
    "VehicleDecoder",
    "VehicleMatchResult",
    "VehicleSpec",
    "VehicleVocab",
    "build_vehicle_vocab",
    "compare_vehicle",
    "decode_synthetic_chassis",
    "encode_synthetic_chassis",
    "is_synthetic_chassis",
    "load_vehicle_vocab",
]
