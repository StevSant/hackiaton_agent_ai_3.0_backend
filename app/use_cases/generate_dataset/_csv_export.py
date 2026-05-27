"""§2.8 CSV export — emits the 5 tables with Spanish snake_case headers.

Writes into ``data/synthetic/`` (created if absent).
All identifiers are synthetic; no real PII (§2.10).
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from app.schemas.claim import ClaimDetail
from app.use_cases.generate_dataset._claim_builder import claim_to_row


def _hash8(seed: str) -> str:
    return hashlib.sha1(seed.encode()).hexdigest()[:8].upper()  # noqa: S324


def _poliza_row(claim: ClaimDetail) -> dict[str, Any]:
    return {
        "id_poliza": claim.poliza,
        "id_asegurado": claim.asegurado_id,
        "ramo": claim.ramo,
        "fecha_inicio": str(claim.fecha_ocurrencia),    # approximation
        "fecha_fin": "",
        "prima": round(claim.suma_asegurada * 0.025, 2),
        "suma_asegurada": claim.suma_asegurada,
        "deducible": round(claim.suma_asegurada * 0.05, 2),
        "canal_venta": "Agente",
        "ciudad": claim.ciudad,
        "estado_poliza": "Vigente",
    }


def _asegurado_row(claim: ClaimDetail) -> dict[str, Any]:
    return {
        "id_asegurado": claim.asegurado_id,
        "segmento": "Personal",
        "antiguedad": 3,
        "ciudad": claim.ciudad,
        "num_polizas": 1,
        "reclamos_ultimos_12_meses": sum(
            1 for a in claim.alertas if a.code in {"FS-03", "FS-04", "FS-05"}
        ),
        "mora_actual": "no",
        "score_cliente_simulado": max(0, 100 - claim.score),
    }


def _proveedor_row(claim: ClaimDetail, idx: int) -> dict[str, Any] | None:
    if claim.proveedor is None:
        return None
    prov_id = f"PROV-{_hash8(claim.proveedor)[:6]}"
    return {
        "id_proveedor": prov_id,
        "tipo": "Taller de reparación",
        "ciudad": claim.ciudad,
        "reclamos_asociados": sum(
            a.puntos for a in claim.alertas if a.code == "FS-07"
        ),
        "monto_promedio_reclamado": claim.monto_reclamado,
        "porcentaje_casos_observados": 0.0,
        "antiguedad": 5,
    }


def _documento_rows(claim: ClaimDetail) -> list[dict[str, Any]]:
    rows = []
    for i, doc in enumerate(claim.documentos):
        rows.append(
            {
                "id_documento": f"DOC-{_hash8(claim.id + str(i))[:8]}",
                "id_siniestro": claim.id,
                "tipo_documento": doc.tipo,
                "entregado": "no" if doc.falta else "sí",
                "legible": "sí",
                "fecha_emision": str(claim.fecha_reporte),
                "inconsistencia_detectada": "no",
                "observacion": "",
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def export_csvs(claims: list[ClaimDetail], out_dir: Path) -> None:
    """Write the 5 §2.8 CSV files under *out_dir*."""
    out_dir.mkdir(parents=True, exist_ok=True)

    sin_rows = [claim_to_row(c) for c in claims]
    pol_seen: set[str] = set()
    pol_rows: list[dict[str, Any]] = []
    ase_seen: set[str] = set()
    ase_rows: list[dict[str, Any]] = []
    prov_seen: set[str] = set()
    prov_rows: list[dict[str, Any]] = []
    doc_rows: list[dict[str, Any]] = []

    for idx, claim in enumerate(claims):
        if claim.poliza not in pol_seen:
            pol_seen.add(claim.poliza)
            pol_rows.append(_poliza_row(claim))

        if claim.asegurado_id not in ase_seen:
            ase_seen.add(claim.asegurado_id)
            ase_rows.append(_asegurado_row(claim))

        if claim.proveedor and claim.proveedor not in prov_seen:
            prov_seen.add(claim.proveedor)
            row = _proveedor_row(claim, idx)
            if row:
                prov_rows.append(row)

        doc_rows.extend(_documento_rows(claim))

    _write_csv(out_dir / "siniestros.csv", sin_rows)
    _write_csv(out_dir / "polizas.csv", pol_rows)
    _write_csv(out_dir / "asegurados.csv", ase_rows)
    _write_csv(out_dir / "beneficiarios_proveedores.csv", prov_rows)
    _write_csv(out_dir / "documentos.csv", doc_rows)
