"""Tests for the XLSX claims parser.

All tests are synchronous (the parser is sync). Fixtures build workbooks
in-memory using openpyxl so no on-disk file I/O is needed.
"""

from __future__ import annotations

import io
from datetime import date, datetime

import openpyxl
import pytest

from app.schemas.claim import ClaimDetail
from app.use_cases.import_claims._xlsx_parser import parse_xlsx

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_COLUMNS = [
    "id",
    "ramo",
    "cobertura",
    "asegurado_id",
    "poliza",
    "ciudad",
    "fecha_ocurrencia",
    "fecha_reporte",
    "monto_reclamado",
]

_FULL_COLUMNS = [
    "id",
    "ramo",
    "cobertura",
    "asegurado",
    "asegurado_id",
    "poliza",
    "ciudad",
    "fecha_ocurrencia",
    "fecha_reporte",
    "fecha_inicio_poliza",
    "fecha_fin_poliza",
    "monto_reclamado",
    "suma_asegurada",
    "estado",
    "sucursal",
    "proveedor",
    "descripcion",
    "score",
    "nivel",
]


def _make_xlsx(
    headers: list[str],
    rows: list[list[object]],
    *,
    sheet_name: str = "claims",
) -> bytes:
    """Create an in-memory .xlsx with one sheet and return its bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name  # type: ignore[union-attr]
    ws.append(headers)  # type: ignore[union-attr]
    for row in rows:
        ws.append(row)  # type: ignore[union-attr]
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def _minimal_data_row() -> list[object]:
    """A single data row that satisfies all required columns."""
    return [
        "SIN-TEST-001",     # id
        "Vehículos",        # ramo
        "Daños",            # cobertura
        "ASE-TEST-001",     # asegurado_id
        "POL-TEST-001",     # poliza
        "Quito",            # ciudad
        "2026-05-01",       # fecha_ocurrencia
        "2026-05-03",       # fecha_reporte
        15000.0,            # monto_reclamado
    ]


# ---------------------------------------------------------------------------
# Smoke test: generated XLSX files parse correctly
# ---------------------------------------------------------------------------


def test_smoke_generated_xlsx_files() -> None:
    """Every generated demo XLSX must parse into exactly 1 ClaimDetail."""
    from pathlib import Path

    xlsx_dir = (
        Path(__file__).parent.parent.parent.parent  # repo root
        / "data" / "casos_demo" / "xlsx"
    )
    # Cases are classified by ramo (xlsx/<ramo>/caso_*.xlsx) — recurse.
    xlsx_files = sorted(xlsx_dir.rglob("caso_*.xlsx"))
    assert xlsx_files, f"No demo xlsx files found under {xlsx_dir}"

    for xlsx_path in xlsx_files:
        content = xlsx_path.read_bytes()
        claims = parse_xlsx(content)
        assert len(claims) == 1, f"{xlsx_path.name}: expected 1 claim, got {len(claims)}"
        assert isinstance(claims[0], ClaimDetail)
        assert claims[0].id.startswith("SIN-DEMO-")


# ---------------------------------------------------------------------------
# Date cell test: openpyxl date/datetime objects are parsed correctly
# ---------------------------------------------------------------------------


def test_date_cell_type_parses_correctly() -> None:
    """Date cells stored as native Excel date objects should parse to date fields."""
    headers = _FULL_COLUMNS
    row: list[object] = [
        "SIN-DATE-001",
        "Vehículos",
        "Daños",
        "Juan Pérez",
        "ASE-DATE-001",
        "POL-DATE-001",
        "Guayaquil",
        date(2026, 4, 15),       # fecha_ocurrencia — native date object
        datetime(2026, 4, 17, 9, 30),  # fecha_reporte — datetime object
        date(2025, 10, 1),       # fecha_inicio_poliza
        date(2026, 10, 1),       # fecha_fin_poliza
        3200.0,
        8000.0,
        "Reserva",
        "Guayaquil Centro",
        "Taller ABC",
        "Daño lateral leve",
        0,
        "verde",
    ]
    content = _make_xlsx(headers, [row])
    claims = parse_xlsx(content)

    assert len(claims) == 1
    c = claims[0]
    assert c.fecha_ocurrencia == date(2026, 4, 15)
    assert c.fecha_reporte == date(2026, 4, 17)
    assert c.fecha_inicio_poliza == date(2025, 10, 1)
    assert c.fecha_fin_poliza == date(2026, 10, 1)


# ---------------------------------------------------------------------------
# Empty row test: blank rows are skipped
# ---------------------------------------------------------------------------


def test_empty_rows_are_skipped() -> None:
    """Completely empty rows between data rows must be ignored."""
    headers = _REQUIRED_COLUMNS
    row1 = _minimal_data_row()
    empty: list[object] = [None] * len(headers)
    row2: list[object] = [
        "SIN-TEST-002",
        "Vehículos",
        "Daños",
        "ASE-TEST-002",
        "POL-TEST-002",
        "Cuenca",
        "2026-04-10",
        "2026-04-11",
        9000.0,
    ]
    content = _make_xlsx(headers, [row1, empty, row2])
    claims = parse_xlsx(content)

    assert len(claims) == 2
    assert {c.id for c in claims} == {"SIN-TEST-001", "SIN-TEST-002"}


# ---------------------------------------------------------------------------
# Missing required column test: ValueError with an informative message
# ---------------------------------------------------------------------------


def test_missing_required_column_raises_value_error() -> None:
    """Omitting a required column must raise ValueError naming the missing col(s)."""
    # Drop 'monto_reclamado' from the header.
    incomplete_headers = [c for c in _REQUIRED_COLUMNS if c != "monto_reclamado"]
    row = [
        "SIN-FAIL-001",
        "Vehículos",
        "Daños",
        "ASE-FAIL-001",
        "POL-FAIL-001",
        "Quito",
        "2026-05-01",
        "2026-05-03",
        # monto_reclamado deliberately omitted
    ]
    content = _make_xlsx(incomplete_headers, [row])

    with pytest.raises(ValueError, match="monto_reclamado"):
        parse_xlsx(content)


# ---------------------------------------------------------------------------
# Number cell test: integer and float cells convert without loss
# ---------------------------------------------------------------------------


def test_number_cells_convert_correctly() -> None:
    """Numeric Excel cells (int/float) should survive the str-conversion round-trip."""
    headers = _FULL_COLUMNS
    row: list[object] = [
        "SIN-NUM-001",
        "Vehículos",
        "Daños",
        "Maria Lopez",
        "ASE-NUM-001",
        "POL-NUM-001",
        "Quito",
        "2026-05-01",
        "2026-05-03",
        "",  # fecha_inicio_poliza optional
        "",  # fecha_fin_poliza optional
        22500,        # integer cell for monto_reclamado
        25000.50,     # float cell for suma_asegurada
        "Reserva",
        "Quito Norte",
        "",
        "Descripción de prueba",
        42,           # integer score
        "amarillo",
    ]
    content = _make_xlsx(headers, [row])
    claims = parse_xlsx(content)

    assert len(claims) == 1
    c = claims[0]
    assert c.monto_reclamado == pytest.approx(22500.0)
    assert c.suma_asegurada == pytest.approx(25000.50)
    assert c.score == 42
