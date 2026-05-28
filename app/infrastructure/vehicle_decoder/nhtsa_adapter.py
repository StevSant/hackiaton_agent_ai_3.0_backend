"""VehicleDecoder backed by the NHTSA vPIC public VIN registry.

Decodes a real 17-char VIN by calling NHTSA's free vPIC API (no API key). Make /
Model / ModelYear are projected into a ``VehicleSpec``. Any failure — transport
error, timeout, malformed payload, blank make — yields ``None`` so scoring never
breaks on a decode miss.

``import httpx`` lives here (infrastructure adapter), never in feature code.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.domain.vehicle_identity import VehicleDecoder, VehicleSpec

logger = logging.getLogger(__name__)


class NhtsaVehicleDecoder(VehicleDecoder):
    """Decode a real VIN against NHTSA vPIC (https://vpic.nhtsa.dot.gov/api)."""

    def __init__(self, *, base_url: str, timeout_s: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    async def decode(self, chassis: str) -> VehicleSpec | None:
        if not chassis:
            return None
        url = f"{self._base_url}/vehicles/DecodeVin/{chassis}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, params={"format": "json"})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("nhtsa decode failed for %s: %s", chassis, exc)
            return None
        return self._parse(payload)

    @staticmethod
    def _parse(payload: object) -> VehicleSpec | None:
        """Project the vPIC ``Results`` rows into a VehicleSpec, or None."""
        if not isinstance(payload, dict):
            return None
        results = payload.get("Results")
        if not isinstance(results, list):
            return None

        fields: dict[str, str] = {}
        for row in results:
            if not isinstance(row, dict):
                continue
            variable = row.get("Variable")
            value = row.get("Value")
            if isinstance(variable, str) and isinstance(value, str):
                fields[variable] = value

        marca = (fields.get("Make") or "").strip()
        modelo = (fields.get("Model") or "").strip()
        anio_raw = (fields.get("Model Year") or "").strip()
        if not marca or not anio_raw:
            return None
        try:
            anio = int(anio_raw)
        except ValueError:
            return None

        return VehicleSpec(
            marca=marca.title(),
            modelo=modelo.title() or "Desconocido",
            anio=anio,
        )


def build_nhtsa_vehicle_decoder() -> NhtsaVehicleDecoder:
    """Construct the NHTSA decoder from settings (URL + timeout)."""
    return NhtsaVehicleDecoder(
        base_url=settings.NHTSA_VPIC_URL,
        timeout_s=settings.VEHICLE_DECODER_TIMEOUT_S,
    )
