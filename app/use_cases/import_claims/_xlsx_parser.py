"""Excel (.xlsx) parser for the claims import endpoint.

Accepts a single-sheet workbook with the same column shape as the CSV parser.
The first row must be the header; subsequent rows are claim records.
Unknown columns are silently ignored; missing required columns raise ValueError.

Date cells are handled natively: openpyxl returns ``datetime.date`` /
``datetime.datetime`` objects which are formatted as ISO strings before being
handed to the shared ``_row_to_claim`` helper (which expects plain strings,
just like the CSV path).

Number cells (Excel "Number" type) arrive as ``float`` or ``int`` from
openpyxl; these are also converted to strings so ``_row_to_claim`` can use
its own ``_parse_float`` / ``_parse_int`` helpers without modification.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

import openpyxl

from app.schemas.claim import ClaimDetail
from app.use_cases.import_claims._parsers import (
    _REQUIRED_CSV_COLS,
    _row_to_claim,
)


def _cell_to_str(value: Any) -> str:
    """Convert an openpyxl cell value to a string suitable for ``_row_to_claim``."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        # Preserve integer representation when possible ("42.0" → "42").
        if value == int(value):
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    return str(value).strip()


def parse_xlsx(content: bytes) -> list[ClaimDetail]:
    """Parse a .xlsx file (one sheet) into ClaimDetail objects.

    Expects the same column shape as parse_csv: first row is the header,
    subsequent rows are claims. Unknown columns are silently ignored.
    Missing required columns raise ValueError.
    """
    try:
        workbook = openpyxl.load_workbook(
            io.BytesIO(content),
            read_only=True,
            data_only=True,  # resolve formulae to their cached values
        )
    except Exception as exc:  # noqa: BLE001 — openpyxl raises many unrelated errors
        raise ValueError(f"Cannot open .xlsx file: {exc}") from exc

    sheet = workbook.active
    if sheet is None:
        raise ValueError(".xlsx file has no active sheet")

    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError(".xlsx file is empty")

    # --- Parse header row -------------------------------------------------------
    raw_header = rows[0]
    # Strip BOM from first header cell and normalise to lowercase.
    headers: list[str] = []
    for idx, cell in enumerate(raw_header):
        col_name = _cell_to_str(cell).lstrip("﻿").strip().lower()
        if idx == 0:
            col_name = col_name.lstrip("﻿")
        headers.append(col_name)

    normalised_headers = {h for h in headers if h}
    missing_required = _REQUIRED_CSV_COLS - normalised_headers
    if missing_required:
        raise ValueError(
            f"XLSX is missing required column(s): {', '.join(sorted(missing_required))}"
        )

    # --- Parse data rows --------------------------------------------------------
    claims: list[ClaimDetail] = []
    for row_num, raw_row in enumerate(rows[1:], start=2):
        # Skip completely empty rows.
        if all(cell is None for cell in raw_row):
            continue

        row: dict[str, str] = {
            col: _cell_to_str(val)
            for col, val in zip(headers, raw_row, strict=False)
            if col  # ignore unnamed columns
        }

        try:
            claims.append(_row_to_claim(row, row_num))
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Row {row_num}: {exc}") from exc

    workbook.close()
    return claims
