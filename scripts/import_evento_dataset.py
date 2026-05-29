"""import_evento_dataset — ingest the 5-sheet evento v2 xlsx into the DB.

Reads all 5 sheets from the synthetic dataset, upserts every entity into the
relational tables, and rescores each claim with the canonical rules engine so
the rules fire with dataset ground truth (en_lista_restrictiva, reclamos_rc_sin_tercero,
similitud_narrativa_max) rather than heuristics derived from unrelated rows.

Usage::

    uv run python scripts/import_evento_dataset.py
    uv run python scripts/import_evento_dataset.py path/to/other.xlsx

Run AFTER applying the 0021_evento_fields Alembic migration.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap — lets the script run from the repo root without `pip install`
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

_DEFAULT_XLSX = (
    _REPO_ROOT
    / "data"
    / "Data set documentos evento"
    / "Evento Datasets_Sinteticos_Fraude_500_v2.xlsx"
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sheet parsing helpers
# ---------------------------------------------------------------------------


def _parse_bool(val: Any, *, truthy: str = "Sí") -> bool | None:
    """'Sí'/'No' → True/False; None/'—'/missing → None."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("—", "", "None", "nan"):
        return None
    return s.lower() == truthy.lower()


def _parse_optional_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return None if s in ("—", "", "None", "nan") else s


def _parse_optional_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        import math
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _parse_optional_int(val: Any) -> int | None:
    f = _parse_optional_float(val)
    return None if f is None else round(f)


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val if isinstance(val, date) else val.date()
    s = str(val).strip()
    if s in ("—", "", "None", "nan"):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _find_header_row(rows: list[tuple], *candidates: str) -> int:
    """Return the index of the first row whose cells include any candidate string."""
    for i, row in enumerate(rows[:5]):
        cells = {str(c).strip() for c in row if c is not None}
        if cells.intersection(candidates):
            return i
    return 0  # fallback: row 0


def _rows_to_dicts(rows: list[tuple], header_idx: int) -> list[dict[str, Any]]:
    headers = [
        str(c).strip() if c is not None else f"_col{i}"
        for i, c in enumerate(rows[header_idx])
    ]
    out = []
    for row in rows[header_idx + 1:]:
        d = {h: row[i] if i < len(row) else None for i, h in enumerate(headers)}
        # Skip blank rows (all None)
        if all(v is None for v in d.values()):
            continue
        out.append(d)
    return out


def _load_sheet(path: Path, sheet_name: str, *header_candidates: str) -> list[dict[str, Any]]:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header_idx = _find_header_row(rows, *header_candidates)
    return _rows_to_dicts(rows, header_idx)


# ---------------------------------------------------------------------------
# Row → ORM mappers
# ---------------------------------------------------------------------------


def _map_proveedor(row: dict) -> dict[str, Any]:
    return {
        "id_proveedor": str(row.get("ID Proveedor", "")).strip(),
        "nombre": _parse_optional_str(row.get("Nombre Proveedor")),
        "tipo": _parse_optional_str(row.get("Tipo")) or "Proveedor",
        "ciudad": _parse_optional_str(row.get("Ciudad")) or "",
        "reclamos_asociados": _parse_optional_int(row.get("N° Siniestros Asociados")) or 0,
        "monto_promedio_reclamado": _parse_optional_float(row.get("Promedio Monto ($)")) or 0.0,
        "porcentaje_casos_observados": 0.0,  # aggregated post-ingest; not in this sheet
        "antiguedad": None,
        # New ground-truth fields (0021_evento_fields)
        "en_lista_restrictiva": _parse_bool(row.get("En Lista Restrictiva")),
        "motivo_restriccion": _parse_optional_str(row.get("Motivo Restricción")),
    }


def _map_asegurado(row: dict) -> dict[str, Any]:
    return {
        "id_asegurado": str(row.get("ID Asegurado", "")).strip(),
        "nombre": _parse_optional_str(row.get("Nombres Asegurado")),
        "segmento": _parse_optional_str(row.get("Segmento")),
        "antiguedad": _parse_optional_int(row.get("Antigüedad (años)")),
        "ciudad": _parse_optional_str(row.get("Ciudad")) or "",
        "num_polizas": _parse_optional_int(row.get("N° Pólizas Activas")) or 0,
        "reclamos_ultimos_12_meses": (
            _parse_optional_int(row.get("N° Reclamos Últimos 12 Meses")) or 0
        ),
        "mora_actual": False,
        "score_cliente_simulado": None,
        # New ground-truth fields (0021_evento_fields)
        "reclamos_historico_total": _parse_optional_int(row.get("N° Reclamos Histórico Total")),
        "reclamos_rc_sin_tercero": _parse_optional_int(row.get("Reclamos RC sin Tercero")),
        "perfil_riesgo": _parse_optional_str(row.get("Perfil Riesgo Histórico")),
    }


def _map_poliza(row: dict) -> dict[str, Any]:
    return {
        "id_poliza": str(row.get("ID Póliza", "")).strip(),
        "id_asegurado": str(row.get("ID Asegurado", "")).strip(),
        "ramo": _parse_optional_str(row.get("Ramo")) or "",
        "fecha_inicio": _parse_date(row.get("Fecha Inicio")),
        "fecha_fin": _parse_date(row.get("Fecha Fin")),
        "suma_asegurada": _parse_optional_float(row.get("Suma Asegurada ($)")) or 0.0,
        "prima": _parse_optional_float(row.get("Prima Anual ($)")) or 0.0,
        "deducible": 0.0,
        "canal_venta": _parse_optional_str(row.get("Canal Venta")),
        "ciudad": "",  # not in this sheet; will be filled from siniestro city
        "estado_poliza": _parse_optional_str(row.get("Estado Póliza")) or "vigente",
    }


def _map_siniestro(row: dict) -> dict[str, Any]:
    id_sin = str(row.get("ID Siniestro", "")).strip()
    docs_completos = _parse_bool(row.get("Docs Completos"))
    fecha_ocurrencia = _parse_date(row.get("Fecha Ocurrencia"))
    fecha_reporte = _parse_date(row.get("Fecha Reporte"))

    if fecha_ocurrencia and fecha_reporte:
        dias_reporte = (fecha_reporte - fecha_ocurrencia).days
    else:
        dias_reporte = _parse_optional_int(row.get("Días Ocurr→Reporte")) or 0

    return {
        "id_siniestro": id_sin,
        "id_poliza": str(row.get("ID Póliza", "")).strip(),
        "id_asegurado": str(row.get("ID Asegurado", "")).strip(),
        "workspace_id": None,
        "ramo": _parse_optional_str(row.get("Ramo")) or "",
        "cobertura": _parse_optional_str(row.get("Cobertura")) or "",
        "fecha_ocurrencia": fecha_ocurrencia,
        "fecha_reporte": fecha_reporte,
        "monto_reclamado": _parse_optional_float(row.get("Monto Reclamado ($)")) or 0.0,
        "monto_estimado": _parse_optional_float(row.get("Monto Estimado ($)")),
        "monto_pagado": _parse_optional_float(row.get("Monto Pagado ($)")),
        "estado": _parse_optional_str(row.get("Estado")) or "Reserva",
        "sucursal": _parse_optional_str(row.get("Sucursal")) or "",
        "descripcion": _parse_optional_str(row.get("Descripción del Evento")) or "",
        "documentos_completos": docs_completos if docs_completos is not None else False,
        "beneficiario": _parse_optional_str(row.get("ID Proveedor")),
        "dias_desde_inicio_poliza": _parse_optional_int(row.get("Días desde Inicio Póliza")),
        "dias_desde_fin_poliza": _parse_optional_int(row.get("Días hasta Fin Póliza")),
        "dias_entre_ocurrencia_reporte": dias_reporte,
        "historial_siniestros_asegurado": (
            _parse_optional_int(row.get("N° Reclamos Previos Asegurado")) or 0
        ),
        "etiqueta_fraude_simulada": 0,
        "placa": _parse_optional_str(row.get("Placa Vehículo Asegurado")),
        "chasis": None,
        "motor": None,
        "marca": None,
        "modelo": None,
        "anio": None,
        "latitude": None,
        "longitude": None,
        "signals": {},
        "resumen_editado": None,
        # New ground-truth fields (0021_evento_fields)
        "numero_parte_policial": _parse_optional_str(row.get("Número Parte Policial")),
        "similitud_narrativa_max": _parse_optional_float(row.get("Similitud Narrativa Máx.")),
    }


def _map_documento(row: dict) -> dict[str, Any]:
    return {
        "id_documento": str(row.get("ID Documento", "")).strip(),
        "id_siniestro": str(row.get("ID Siniestro", "")).strip(),
        "tipo_documento": _parse_optional_str(row.get("Tipo Documento")) or "Documento",
        "entregado": True,
        "legible": True,
        "fecha_emision": None,
        "inconsistencia_detectada": False,
        "observacion": None,
        "storage_path": None,
        "filename": _parse_optional_str(row.get("Nombre Archivo PDF")),
        "content_type": None,
    }


# ---------------------------------------------------------------------------
# Dry-run parse (no DB) — called from CLI for smoke-test
# ---------------------------------------------------------------------------


def parse_only(xlsx_path: Path) -> None:
    """Parse all sheets and print row counts + 1 sample per entity. No DB."""
    print(f"\nParsing: {xlsx_path}")

    prov_rows = _load_sheet(xlsx_path, "4_Proveedores", "ID Proveedor")
    aseg_rows = _load_sheet(xlsx_path, "3_Asegurados", "ID Asegurado")
    pol_rows = _load_sheet(xlsx_path, "2_Polizas", "ID Póliza", "ID Poliza")
    sin_rows = _load_sheet(xlsx_path, "1_Siniestros", "ID Siniestro")
    doc_rows = _load_sheet(xlsx_path, "5_Documentos", "ID Documento")

    print(f"  4_Proveedores : {len(prov_rows)} rows")
    print(f"  3_Asegurados  : {len(aseg_rows)} rows")
    print(f"  2_Polizas     : {len(pol_rows)} rows")
    print(f"  1_Siniestros  : {len(sin_rows)} rows")
    print(f"  5_Documentos  : {len(doc_rows)} rows")

    if prov_rows:
        s = _map_proveedor(prov_rows[0])
        print(f"\n  Sample Proveedor: id={s['id_proveedor']!r} nombre={s['nombre']!r}"
              f" en_lista_restrictiva={s['en_lista_restrictiva']}")
    if aseg_rows:
        s = _map_asegurado(aseg_rows[0])
        print(f"  Sample Asegurado: id={s['id_asegurado']!r} nombre={s['nombre']!r}"
              f" reclamos_rc={s['reclamos_rc_sin_tercero']} perfil={s['perfil_riesgo']!r}")
    if sin_rows:
        s = _map_siniestro(sin_rows[0])
        print(f"  Sample Siniestro: id={s['id_siniestro']!r} cobertura={s['cobertura']!r}"
              f" sim_max={s['similitud_narrativa_max']} parte={s['numero_parte_policial']!r}")


# ---------------------------------------------------------------------------
# DB upsert helpers
# ---------------------------------------------------------------------------


async def _upsert_proveedores(session: Any, rows: list[dict]) -> int:
    from app.infrastructure.db.models.proveedor import Proveedor
    count = 0
    for d in rows:
        if not d["id_proveedor"]:
            continue
        obj = Proveedor(**d)
        await session.merge(obj)
        count += 1
    await session.flush()
    return count


async def _upsert_asegurados(session: Any, rows: list[dict]) -> int:
    from app.infrastructure.db.models.asegurado import Asegurado
    count = 0
    for d in rows:
        if not d["id_asegurado"]:
            continue
        obj = Asegurado(**d)
        await session.merge(obj)
        count += 1
    await session.flush()
    return count


async def _upsert_polizas(session: Any, rows: list[dict], ciudad_by_poliza: dict[str, str]) -> int:
    from app.infrastructure.db.models.poliza import Poliza
    count = 0
    for d in rows:
        if not d["id_poliza"]:
            continue
        # Fill ciudad from the siniestros sheet when available
        d["ciudad"] = ciudad_by_poliza.get(d["id_poliza"], "")
        obj = Poliza(**d)
        await session.merge(obj)
        count += 1
    await session.flush()
    return count


async def _upsert_siniestros(session: Any, rows: list[dict]) -> int:
    from app.infrastructure.db.models.siniestro import Siniestro
    count = 0
    for d in rows:
        if not d["id_siniestro"]:
            continue
        obj = Siniestro(**d)
        await session.merge(obj)
        count += 1
    await session.flush()
    return count


async def _upsert_documentos(session: Any, rows: list[dict]) -> int:
    from app.infrastructure.db.models.documento import Documento
    count = 0
    for d in rows:
        if not d["id_documento"] or not d["id_siniestro"]:
            continue
        obj = Documento(**d)
        await session.merge(obj)
        count += 1
    await session.flush()
    return count


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

_SEVERITY_BY_TIER = {"rojo": "high", "amarillo": "med", "verde": "low"}
_PROGRESS_INTERVAL = 50


async def _score_batch(
    session: Any,
    sin_ids: list[str],
) -> dict[str, int]:
    """Score each claim using the rules engine (no LLM). Returns tier counts."""
    from sqlalchemy import select as sa_select

    from app.infrastructure.db.models.asegurado import Asegurado
    from app.infrastructure.db.models.claim_score import ClaimScore
    from app.infrastructure.db.models.documento import Documento
    from app.infrastructure.db.models.poliza import Poliza
    from app.infrastructure.db.models.proveedor import Proveedor
    from app.infrastructure.db.models.siniestro import Siniestro
    from app.use_cases._rescore_one import rescore_one
    from app.use_cases.load_dataset._mapping import rows_to_claim_detail

    tiers: dict[str, int] = {"verde": 0, "amarillo": 0, "rojo": 0}
    total = len(sin_ids)
    for idx, sin_id in enumerate(sin_ids):
        try:
            sin: Siniestro | None = await session.get(Siniestro, sin_id)
            if sin is None:
                continue
            pol: Poliza | None = await session.get(Poliza, sin.id_poliza)
            aseg: Asegurado | None = await session.get(Asegurado, sin.id_asegurado)
            prov: Proveedor | None = (
                await session.get(Proveedor, sin.beneficiario)
                if sin.beneficiario else None
            )
            docs_result = await session.execute(
                sa_select(Documento).where(Documento.id_siniestro == sin_id)
            )
            docs = list(docs_result.scalars().all())
            score_row: ClaimScore | None = (
                await session.execute(
                    sa_select(ClaimScore).where(ClaimScore.claim_id == sin_id)
                )
            ).scalars().first()

            detail = rows_to_claim_detail(sin, pol, score_row, docs, prov, asegurado=aseg)
            _scored, risk = await rescore_one(session, detail)
            tiers[risk.tier.value] = tiers.get(risk.tier.value, 0) + 1
        except Exception as exc:
            logger.warning("scoring: failed for %s: %s", sin_id, exc)

        if (idx + 1) % _PROGRESS_INTERVAL == 0 or (idx + 1) == total:
            await session.commit()
            logger.info("scoring: %d/%d scored", idx + 1, total)

    return tiers


# ---------------------------------------------------------------------------
# Main async runner
# ---------------------------------------------------------------------------


async def _run(xlsx_path: Path, *, dry_run: bool = False) -> None:
    from app.infrastructure.db.engine import create_engine, create_session_factory

    # Parse all sheets up-front (no DB required)
    logger.info("Parsing %s ...", xlsx_path)
    prov_rows_raw = _load_sheet(xlsx_path, "4_Proveedores", "ID Proveedor")
    aseg_rows_raw = _load_sheet(xlsx_path, "3_Asegurados", "ID Asegurado")
    pol_rows_raw = _load_sheet(xlsx_path, "2_Polizas", "ID Póliza", "ID Poliza")
    sin_rows_raw = _load_sheet(xlsx_path, "1_Siniestros", "ID Siniestro")
    doc_rows_raw = _load_sheet(xlsx_path, "5_Documentos", "ID Documento")

    prov_rows = [_map_proveedor(r) for r in prov_rows_raw if r.get("ID Proveedor")]
    aseg_rows = [_map_asegurado(r) for r in aseg_rows_raw if r.get("ID Asegurado")]
    pol_rows = [_map_poliza(r) for r in pol_rows_raw if r.get("ID Póliza") or r.get("ID Poliza")]
    sin_rows = [_map_siniestro(r) for r in sin_rows_raw if r.get("ID Siniestro")]
    doc_rows = [_map_documento(r) for r in doc_rows_raw if r.get("ID Documento")]

    # Build ciudad index from siniestros (used to fill polizas.ciudad)
    ciudad_by_poliza: dict[str, str] = {}
    for s in sin_rows:
        if s["id_poliza"] and s["sucursal"]:
            ciudad_by_poliza[s["id_poliza"]] = s["sucursal"]

    logger.info(
        "Parsed: %d proveedores, %d asegurados, %d pólizas, %d siniestros, %d documentos",
        len(prov_rows), len(aseg_rows), len(pol_rows), len(sin_rows), len(doc_rows),
    )

    if dry_run:
        logger.info("Dry-run mode — no DB writes.")
        return

    engine = create_engine()
    factory = create_session_factory(engine)

    try:
        async with factory() as session:
            # Commit after EACH phase so a slow/dropped Supabase connection during
            # a later phase can't roll back everything already written.
            logger.info("Upserting proveedores ...")
            n_prov = await _upsert_proveedores(session, prov_rows)
            await session.commit()

            logger.info("Upserting asegurados ...")
            n_aseg = await _upsert_asegurados(session, aseg_rows)
            await session.commit()

            logger.info("Upserting pólizas ...")
            n_pol = await _upsert_polizas(session, pol_rows, ciudad_by_poliza)
            await session.commit()

            logger.info("Upserting siniestros ...")
            n_sin = await _upsert_siniestros(session, sin_rows)
            await session.commit()

            logger.info("Upserting documentos ...")
            n_doc = await _upsert_documentos(session, doc_rows)
            await session.commit()
            logger.info(
                "Upsert complete — prov=%d aseg=%d pol=%d sin=%d doc=%d",
                n_prov, n_aseg, n_pol, n_sin, n_doc,
            )

        # Score in a fresh session so the upserted rows are visible.
        logger.info("Scoring %d siniestros (rules engine only, no LLM) ...", len(sin_rows))
        sin_ids = [r["id_siniestro"] for r in sin_rows]
        async with factory() as session:
            tiers = await _score_batch(session, sin_ids)

        print("\n── Import summary ──────────────────────────────")
        print(f"  Proveedores upserted : {n_prov}")
        print(f"  Asegurados  upserted : {n_aseg}")
        print(f"  Pólizas     upserted : {n_pol}")
        print(f"  Siniestros  upserted : {n_sin}")
        print(f"  Documentos  upserted : {n_doc}")
        print("\n── Tier breakdown (after scoring) ──────────────")
        total_scored = sum(tiers.values())
        denom = max(total_scored, 1)
        v = tiers.get("verde", 0)
        a = tiers.get("amarillo", 0)
        r = tiers.get("rojo", 0)
        print(f"  Verde    : {v:4d}  ({v / denom * 100:.1f}%)")
        print(f"  Amarillo : {a:4d}  ({a / denom * 100:.1f}%)")
        print(f"  Rojo     : {r:4d}  ({r / denom * 100:.1f}%)")
        print(f"  Total scored: {total_scored}")
        print("────────────────────────────────────────────────\n")

    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Ingest the 5-sheet evento v2 xlsx into the fraud-detection DB."
    )
    parser.add_argument(
        "xlsx_path",
        nargs="?",
        default=str(_DEFAULT_XLSX),
        help="Path to the xlsx file (default: data/Data set documentos evento/Evento...v2.xlsx)",
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Parse the file and print counts/samples without touching the DB.",
    )
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx_path)
    if not xlsx_path.exists():
        print(f"ERROR: file not found: {xlsx_path}", file=sys.stderr)
        return 1

    if args.parse_only:
        parse_only(xlsx_path)
        return 0

    asyncio.run(_run(xlsx_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
