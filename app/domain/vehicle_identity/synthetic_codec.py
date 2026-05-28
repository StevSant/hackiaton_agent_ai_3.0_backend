"""Deterministic synthetic chassis codec — encode/decode a VehicleSpec.

Synthetic claims have no real-world VIN, so we mint a stable, reversible 17-char
VIN-like string that *encodes* the (marca, modelo, año) triple. The scheme is a
pure function of the spec + a persisted vocabulary — no randomness — so
``decode(encode(spec)) == spec`` for ANY marca/modelo present in the vocab.

Like a real VIN encodes its manufacturer via a registry-issued code, marca/modelo
are encoded as their INDEX into ``data/config/vehicle_vocab.json`` (built from the
distinct makes/models in the data, see ``build_vehicle_vocab``). The codec never
depends on the generator pools — it depends on the persisted vocab, so real DB
values like ``Toyota / RAV4`` round-trip once they're in the vocab.

Layout of the 17 characters (uppercase, VIN alphabet minus I/O/Q):

    pos 0       : "Z"          fixed synthetic marker (lets the hybrid router
                               distinguish our minted chassis from a real VIN)
    pos 1-2     : MM           marca index in the vocab, base-36, 2 chars (00..ZZ)
    pos 3-4     : NN           modelo index in the vocab, base-36, 2 chars
    pos 5-8     : YYYY         model year, 4 decimal digits
    pos 9-15    : CHECK        7-char deterministic filler derived from the
                               payload (sha256) so the string looks VIN-shaped
                               and tampering is detectable
    pos 16      : "S"          fixed synthetic tail marker

Two base-36 chars hold up to 36*36 = 1296 distinct indices per dimension —
plenty for the make/model vocabulary. Indices are stable because the vocab is
sorted deterministically and committed.
"""

from __future__ import annotations

import hashlib

from app.domain.vehicle_identity.models import VehicleSpec
from app.domain.vehicle_identity.vehicle_vocab import load_vehicle_vocab

# VIN alphabet excludes I, O, Q. Our marker chars (Z, S) are inside it.
SYNTHETIC_PREFIX = "Z"
SYNTHETIC_SUFFIX = "S"
SYNTHETIC_LENGTH = 17

_CHECK_LEN = 7
_INDEX_WIDTH = 2  # base-36 chars per index → max 36**2 = 1296 distinct values
_MAX_INDEX = 36**_INDEX_WIDTH - 1
# base-36 alphabet for compact index encoding (digits + A-Z, never I/O/Q issues
# because we only emit 0-9A-Z and decode the same set).
_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_base36(value: int, width: int) -> str:
    """Encode a non-negative int as a fixed-width base-36 string."""
    chars: list[str] = []
    n = value
    for _ in range(width):
        chars.append(_BASE36[n % 36])
        n //= 36
    return "".join(reversed(chars))


def _from_base36(token: str) -> int:
    """Decode a base-36 string back to an int (inverse of ``_to_base36``)."""
    result = 0
    for ch in token:
        result = result * 36 + _BASE36.index(ch)
    return result


def _check_block(marca_idx: int, modelo_idx: int, anio: int) -> str:
    """Deterministic 7-char filler derived from the payload (no randomness)."""
    payload = f"{marca_idx}:{modelo_idx}:{anio}".encode()
    digest = hashlib.sha256(payload).hexdigest().upper()
    block: list[str] = []
    for ch in digest:
        if ch in _BASE36:
            block.append(ch)
        if len(block) == _CHECK_LEN:
            break
    return "".join(block).ljust(_CHECK_LEN, "0")


def encode_synthetic_chassis(spec: VehicleSpec) -> str:
    """Encode a VehicleSpec into a deterministic 17-char synthetic chassis.

    Raises ``ValueError`` when the spec's marca/modelo are not in the persisted
    vocabulary (run ``build_vehicle_vocab`` first) or when an index overflows the
    2-char base-36 field (vocab > 1296 entries in a dimension).
    """
    vocab = load_vehicle_vocab()
    marca_idx = vocab.index_marca(spec.marca)
    modelo_idx = vocab.index_modelo(spec.modelo)
    if marca_idx > _MAX_INDEX or modelo_idx > _MAX_INDEX:
        raise ValueError(
            "vehicle vocab index overflow: marca/modelo index exceeds "
            f"{_MAX_INDEX}; widen _INDEX_WIDTH to encode this vocabulary"
        )

    body = (
        SYNTHETIC_PREFIX
        + _to_base36(marca_idx, _INDEX_WIDTH)
        + _to_base36(modelo_idx, _INDEX_WIDTH)
        + f"{spec.anio:04d}"
        + _check_block(marca_idx, modelo_idx, spec.anio)
        + SYNTHETIC_SUFFIX
    )
    return body


def is_synthetic_chassis(chassis: str) -> bool:
    """True when *chassis* has the synthetic marker shape minted by this codec."""
    if len(chassis) != SYNTHETIC_LENGTH:
        return False
    up = chassis.upper()
    return up.startswith(SYNTHETIC_PREFIX) and up.endswith(SYNTHETIC_SUFFIX)


def decode_synthetic_chassis(chassis: str) -> VehicleSpec | None:
    """Inverse of ``encode_synthetic_chassis``; None when unparseable.

    Validates the embedded check block so a hand-edited synthetic chassis (a
    tampered position) decodes to ``None`` rather than a silently wrong spec.
    Resolves indices against the SAME persisted vocab used at encode time.
    """
    if not is_synthetic_chassis(chassis):
        return None
    up = chassis.upper()
    try:
        marca_idx = _from_base36(up[1:3])
        modelo_idx = _from_base36(up[3:5])
        anio = int(up[5:9])
        check = up[9:16]
    except (ValueError, IndexError):
        return None

    if check != _check_block(marca_idx, modelo_idx, anio):
        return None

    vocab = load_vehicle_vocab()
    marca = vocab.marca_at(marca_idx)
    modelo = vocab.modelo_at(modelo_idx)
    if marca is None or modelo is None:
        return None

    return VehicleSpec(marca=marca, modelo=modelo, anio=anio)
