"""Generate CSV + XLSX twin samples for each curated demo case.

Recurses the ramo-classified JSONs under ``data/casos_demo/json/<ramo>/`` and
mirrors the ``<ramo>/`` subpath into the output trees:

- ``data/casos_demo/csv/<ramo>/<stem>.csv``   — single-data-row CSV
- ``data/casos_demo/xlsx/<ramo>/<stem>.xlsx`` — single-data-row XLSX (sheet "claims")

Column order matches ``data/samples/claims.sample.csv``. Fields that exist
only in the JSON format (vehiculo, documentos, alertas, score, nivel) are
either included as flat scalars when they map to a CSV column (score, nivel)
or silently omitted (nested objects like vehiculo, documentos).

Usage::

    uv run python scripts/generate_xlsx_samples.py

Run from the repository root (``hackiaton_agent_ai_3.0_backend/``).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import openpyxl

# Progress lines print ✓ — force UTF-8 so it doesn't crash on Windows cp1252.
sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Column order — matches claims.sample.csv and the _parsers.py docstring.
# Fields present in the JSON but not representable as flat CSV are omitted.
# ---------------------------------------------------------------------------
CSV_COLUMNS = [
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


def _json_to_row(data: dict) -> dict[str, str]:
    """Flatten a ClaimDetail-shaped JSON dict into a CSV-compatible row."""
    row: dict[str, str] = {}
    for col in CSV_COLUMNS:
        value = data.get(col)
        if value is None:
            row[col] = ""
        else:
            row[col] = str(value)
    return row


def _write_csv(dest: Path, row: dict[str, str]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def _write_xlsx(dest: Path, row: dict[str, str]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "claims"  # type: ignore[union-attr]
    ws.append(CSV_COLUMNS)  # type: ignore[union-attr]
    ws.append([row[col] for col in CSV_COLUMNS])  # type: ignore[union-attr]
    wb.save(dest)
    wb.close()


def main() -> None:
    repo_root = Path(__file__).parent.parent
    json_dir = repo_root / "data" / "casos_demo" / "json"
    csv_dir = repo_root / "data" / "casos_demo" / "csv"
    xlsx_dir = repo_root / "data" / "casos_demo" / "xlsx"

    # Cases are classified by ramo: json/<ramo>/caso_*.json. Recurse and mirror
    # the <ramo>/ subpath into the csv/ and xlsx/ output trees.
    json_files = sorted(json_dir.rglob("caso_*.json"))
    if not json_files:
        print(f"No JSON files found under {json_dir}")
        return

    for json_path in json_files:
        data: dict = json.loads(json_path.read_text(encoding="utf-8"))
        row = _json_to_row(data)
        rel = json_path.relative_to(json_dir).with_suffix("")  # <ramo>/<stem>

        csv_dest = csv_dir / f"{rel}.csv"
        xlsx_dest = xlsx_dir / f"{rel}.xlsx"

        _write_csv(csv_dest, row)
        _write_xlsx(xlsx_dest, row)

        print(f"  {rel.as_posix()}: csv ✓  xlsx ✓")

    print(f"\nDone. {len(json_files)} cases → {csv_dir}")
    print(f"      {len(json_files)} cases → {xlsx_dir}")


if __name__ == "__main__":
    main()
