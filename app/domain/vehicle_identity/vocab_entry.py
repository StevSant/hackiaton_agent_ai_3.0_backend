"""``VehicleVocab`` — the persisted index ↔ value mapping for marca/modelo.

A frozen value object wrapping the two sorted lists. ``index_marca`` /
``index_modelo`` are the encode-side lookups (raise when a value is absent so the
seed knows to build the vocab first); ``marca_at`` / ``modelo_at`` are the
decode-side reverse lookups (return None on an out-of-range index).
"""

from __future__ import annotations

from pydantic import BaseModel


class VehicleVocab(BaseModel):
    """Sorted, stable vocabulary of makes and models for the synthetic codec."""

    marcas: list[str]
    modelos: list[str]

    def index_marca(self, marca: str) -> int:
        try:
            return self.marcas.index(marca)
        except ValueError as exc:
            raise ValueError(
                f"marca not in vehicle vocab: {marca!r} — run build_vehicle_vocab first"
            ) from exc

    def index_modelo(self, modelo: str) -> int:
        try:
            return self.modelos.index(modelo)
        except ValueError as exc:
            raise ValueError(
                f"modelo not in vehicle vocab: {modelo!r} — run build_vehicle_vocab first"
            ) from exc

    def marca_at(self, idx: int) -> str | None:
        return self.marcas[idx] if 0 <= idx < len(self.marcas) else None

    def modelo_at(self, idx: int) -> str | None:
        return self.modelos[idx] if 0 <= idx < len(self.modelos) else None
