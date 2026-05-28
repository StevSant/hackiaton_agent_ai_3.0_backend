"""Persisted vehicle vocabulary — stable index ↔ value mapping for the codec.

Real VINs encode the manufacturer via a registry-issued code (WMI); we mirror
that idea for synthetic chassis: marca/modelo are encoded as their INDEX into a
persisted, DB-derived vocabulary, not into the generator pools. The vocabulary
is the union of every make/model that actually appears in the data (plus the
generator pools), sorted deterministically and written to a committed JSON file
so indices are stable across runs and across encode/decode.

The JSON shape is ``{"marcas": [...], "modelos": [...]}`` with both lists sorted.
``build_vehicle_vocab`` is called by the seed BEFORE encoding any chassis, so
every declared value in the DB is indexable. ``load_vehicle_vocab`` is the
cached read used at encode/decode time (seed-time and runtime alike).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from app.domain.vehicle_identity.vocab_entry import VehicleVocab

# data/config/ lives at the project root (… / app / domain / vehicle_identity /
# vehicle_vocab.py → parents[3] is the backend root that contains data/).
VEHICLE_VOCAB_PATH: Path = (
    Path(__file__).resolve().parents[3] / "data" / "config" / "vehicle_vocab.json"
)


@lru_cache(maxsize=1)
def load_vehicle_vocab() -> VehicleVocab:
    """Load and cache the persisted vehicle vocabulary.

    Returns an empty vocab when the file is absent (e.g. before the seed has run
    once); encode will then raise a clear error pointing at ``build_vehicle_vocab``.
    """
    if not VEHICLE_VOCAB_PATH.exists():
        return VehicleVocab(marcas=[], modelos=[])
    payload = json.loads(VEHICLE_VOCAB_PATH.read_text(encoding="utf-8"))
    return VehicleVocab(
        marcas=list(payload.get("marcas", [])),
        modelos=list(payload.get("modelos", [])),
    )


def _dedup_sorted(values: Iterable[str]) -> list[str]:
    """Deterministic order: unique, trimmed, non-empty, sorted (case-insensitive)."""
    cleaned = {v.strip() for v in values if v and v.strip()}
    return sorted(cleaned, key=lambda s: (s.casefold(), s))


def build_vehicle_vocab(
    marcas: Iterable[str],
    modelos: Iterable[str],
    *,
    include_pools: bool = True,
) -> VehicleVocab:
    """Union the given values with the existing vocab (+pools), persist, return.

    Args:
        marcas:        make values to ensure are indexable (e.g. distinct DB makes).
        modelos:       model values to ensure are indexable.
        include_pools: also fold in the generator pools so generated data and real
                       data share one vocabulary.

    Side effect: writes ``VEHICLE_VOCAB_PATH`` (pretty, UTF-8, sorted) and clears
    the loader cache so subsequent ``load_vehicle_vocab`` calls see the new file.
    """
    existing = load_vehicle_vocab()
    marca_src: list[str] = [*existing.marcas, *marcas]
    modelo_src: list[str] = [*existing.modelos, *modelos]

    if include_pools:
        # Imported lazily so the domain codec has no hard dependency on the
        # dataset generator at import time (only when building the vocab).
        from app.use_cases.generate_dataset._pools import (
            MARCAS_VEHICULO,
            MODELOS_VEHICULO,
        )

        marca_src.extend(MARCAS_VEHICULO)
        modelo_src.extend(MODELOS_VEHICULO)

    vocab = VehicleVocab(
        marcas=_dedup_sorted(marca_src),
        modelos=_dedup_sorted(modelo_src),
    )

    VEHICLE_VOCAB_PATH.parent.mkdir(parents=True, exist_ok=True)
    VEHICLE_VOCAB_PATH.write_text(
        json.dumps(
            {"marcas": vocab.marcas, "modelos": vocab.modelos},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    load_vehicle_vocab.cache_clear()
    return vocab
