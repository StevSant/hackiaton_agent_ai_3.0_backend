"""File parsers for the claims import endpoint.

Two formats are supported:

JSON
----
A top-level JSON array of ``ClaimDetail``-compatible objects.  This is the same
shape as ``data/synthetic/claims.json`` — validated via Pydantic, so extra keys
are tolerated (ignored).

CSV (denormalised — one row per claim)
--------------------------------------
Columns (all optional unless marked *required*):

  id*                — claim ID (e.g. "SIN-0001")
  ramo*              — insurance line (e.g. "Vehículos")
  cobertura*         — coverage type
  asegurado          — display name (default: derived from asegurado_id)
  asegurado_id*      — insured person ID
  poliza*            — policy ID
  ciudad*            — city
  fecha_ocurrencia*  — ISO date YYYY-MM-DD
  fecha_reporte*     — ISO date YYYY-MM-DD
  fecha_inicio_poliza — ISO date (optional)
  fecha_fin_poliza    — ISO date (optional)
  monto_reclamado*   — float (USD)
  suma_asegurada     — float (default 0.0)
  estado             — claim status (default "Reserva")
  sucursal           — branch (default: derived from ciudad)
  proveedor          — provider/workshop name (optional)
  descripcion        — free-text narrative (optional)
  score              — int 0-100 (optional; re-scored when absent)
  nivel              — "verde"|"amarillo"|"rojo" (optional; re-scored when absent)

Unknown columns are silently ignored.  Missing optional columns use safe defaults.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.schemas.claim import ClaimDetail, ClaimDocument, ClaimReview, ReviewStatus
from app.schemas.risk import Tier
from app.use_cases.load_dataset._display_name_cleanup import (
    _ecuador_provider_name_for_id,
    _looks_like_provider_code,
)

# Columns the CSV parser looks for (case-insensitive match)
_REQUIRED_CSV_COLS = {
    "id", "ramo", "cobertura", "asegurado_id", "poliza",
    "ciudad", "fecha_ocurrencia", "fecha_reporte", "monto_reclamado",
}


def parse_json(content: bytes) -> list[ClaimDetail]:
    """Parse a UTF-8 encoded JSON file → list[ClaimDetail].

    Accepts both:
    - A top-level array:  [{ ... }, ...]
    - A single object:    { ... }  (wrapped into a list)
    """
    try:
        raw: Any = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid JSON file: {exc}") from exc

    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = [raw]
    else:
        raise ValueError(f"Expected a JSON array or object, got {type(raw).__name__}")

    claims: list[ClaimDetail] = []
    for idx, item in enumerate(items):
        try:
            claims.append(ClaimDetail.model_validate(item))
        except ValidationError as exc:
            raise ValueError(f"Row {idx}: {exc}") from exc

    return claims


def parse_csv(content: bytes) -> list[ClaimDetail]:
    """Parse a UTF-8 encoded CSV file → list[ClaimDetail].

    The CSV is expected to have a header row.  Column names are normalised to
    lowercase + strip.  Unknown columns are silently dropped.  Missing optional
    columns fall back to safe Ecuador defaults.

    Raises ``ValueError`` when required columns are absent from the header.
    Per-row errors are raised as ``ValueError`` with the row index included.
    """
    try:
        text = content.decode("utf-8-sig")   # strip BOM if present
    except UnicodeDecodeError:
        text = content.decode("latin-1")     # fallback for Windows-saved files

    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")

    # Normalise header names
    normalised_headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing_required = _REQUIRED_CSV_COLS - normalised_headers
    if missing_required:
        raise ValueError(
            f"CSV is missing required column(s): {', '.join(sorted(missing_required))}"
        )

    claims: list[ClaimDetail] = []
    for row_num, raw_row in enumerate(reader, start=2):  # 1-based, row 1 = header
        # Normalise keys
        row: dict[str, str] = {k.strip().lower(): (v or "").strip()
                                for k, v in raw_row.items() if k}
        try:
            claims.append(_row_to_claim(row, row_num))
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Row {row_num}: {exc}") from exc

    return claims


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_provider_value(raw: str, claim_id: str) -> str | None:
    """Return a display-friendly proveedor name, or None when raw is empty.

    Replaces internal-code strings (``PROV-LISTA-NNN`` / ``PROV-OBS-NNN``) with
    a deterministic Ecuadorian business name so analysts never see codes on the
    triage UI. The substitution mirrors what the synthetic generator does for
    its own claims (`_claim_builder._looks_like_code` path).
    """
    value = (raw or "").strip()
    if not value:
        return None
    if _looks_like_provider_code(value):
        return _ecuador_provider_name_for_id(claim_id)
    return value


def _parse_date(value: str, field: str) -> date:
    """Parse an ISO date string; raise ValueError with a helpful message."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field}: invalid date '{value}' (expected YYYY-MM-DD)"
        ) from exc


def _parse_float(value: str, field: str, default: float = 0.0) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{field}: invalid number '{value}'") from exc


def _parse_int(value: str, field: str, default: int = 0) -> int:
    if not value:
        return default
    try:
        return int(float(value))   # tolerate "42.0" from Excel
    except ValueError as exc:
        raise ValueError(f"{field}: invalid integer '{value}'") from exc


def _row_to_claim(row: dict[str, str], row_num: int) -> ClaimDetail:
    """Convert a normalised CSV row dict to a ClaimDetail."""
    # Required fields
    claim_id = row["id"]
    if not claim_id:
        raise ValueError(f"row {row_num}: 'id' is empty")

    fecha_ocurrencia = _parse_date(row["fecha_ocurrencia"], "fecha_ocurrencia")
    fecha_reporte = _parse_date(row["fecha_reporte"], "fecha_reporte")
    monto_reclamado = _parse_float(row["monto_reclamado"], "monto_reclamado")

    ciudad = row["ciudad"] or "Guayaquil"

    # Optional policy dates
    fi_raw = row.get("fecha_inicio_poliza", "")
    ff_raw = row.get("fecha_fin_poliza", "")
    fecha_inicio_poliza = _parse_date(fi_raw, "fecha_inicio_poliza") if fi_raw else None
    fecha_fin_poliza = _parse_date(ff_raw, "fecha_fin_poliza") if ff_raw else None

    # Derived / defaulted fields
    asegurado_id = row["asegurado_id"]
    asegurado_display = (
        row.get("asegurado", "") or f"Asegurado {asegurado_id[-4:].upper()}"
    )
    sucursal_default = _ciudad_to_sucursal(ciudad)
    estado = row.get("estado", "") or "Reserva"

    # Pre-scored fields (absent → will be scored at upsert time)
    score_raw = row.get("score", "")
    nivel_raw = row.get("nivel", "") or "verde"
    score = _parse_int(score_raw, "score", default=0)
    try:
        nivel = Tier(nivel_raw)
    except ValueError:
        nivel = Tier.verde

    # Build a minimal documentos list — no doc info in the CSV
    documentos = [
        ClaimDocument(tipo="Cédula de identidad", estado="Entregado"),
        ClaimDocument(tipo="Matrícula vehicular", estado="Entregado"),
    ]

    return ClaimDetail(
        id=claim_id,
        ramo=row["ramo"],
        cobertura=row["cobertura"],
        asegurado=asegurado_display,
        asegurado_id=asegurado_id,
        poliza=row["poliza"],
        ciudad=ciudad,
        fecha_ocurrencia=fecha_ocurrencia,
        fecha_reporte=fecha_reporte,
        fecha_inicio_poliza=fecha_inicio_poliza,
        fecha_fin_poliza=fecha_fin_poliza,
        monto_reclamado=monto_reclamado,
        suma_asegurada=_parse_float(row.get("suma_asegurada", ""), "suma_asegurada", 0.0),
        estado=estado,
        sucursal=row.get("sucursal", "") or sucursal_default,
        proveedor=_clean_provider_value(row.get("proveedor", ""), claim_id),
        descripcion=row.get("descripcion", "") or "",
        score=score,
        nivel=nivel,
        documentos=documentos,
        review=ClaimReview(status=ReviewStatus.pendiente),
    )


def _ciudad_to_sucursal(ciudad: str) -> str:
    _MAP = {
        "Guayaquil": "Guayaquil Centro",
        "Quito": "Quito Norte",
    }
    return _MAP.get(ciudad, ciudad)
