"""Persist uploaded files as documento rows and refresh documentos_completos."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.siniestro import Siniestro

_FILENAME_TIPO_HINTS: tuple[tuple[str, str], ...] = (
    ("solicitud", "Solicitud de siniestro"),
    ("denuncia", "Denuncia fiscal"),
    ("acta", "Acta policial"),
    ("matricula", "Matrícula del vehículo"),
    ("cedula", "Cédula de identidad"),
    ("caratula", "Carátula de póliza"),
    ("poliza", "Carátula de póliza"),
    ("licencia", "Licencia de conducir"),
    ("endoso", "Certificado de endoso"),
    ("peritaje", "Peritaje técnico"),
    ("proforma", "Proforma de taller"),
    ("comprobante", "Comprobante de reporte"),
)


def infer_document_tipo(filename: str, *, fallback: str = "Documento adjunto") -> str:
    """Guess document type from filename keywords."""
    lower = filename.lower()
    for hint, tipo in _FILENAME_TIPO_HINTS:
        if hint in lower:
            return tipo
    return fallback


def _normalize_tipo(tipo: str) -> str:
    cleaned = tipo.strip()
    if not cleaned or cleaned.lower() == "otro":
        return "Documento adjunto"
    return cleaned


async def persist_uploaded_document(
    session: AsyncSession,
    *,
    id_siniestro: str,
    tipo: str,
    storage_path: str,
    filename: str,
    content_type: str,
) -> Documento:
    """Upsert a documento row after storage upload and refresh completeness."""
    resolved_tipo = _normalize_tipo(tipo)
    if resolved_tipo == "Documento adjunto":
        resolved_tipo = infer_document_tipo(filename, fallback=resolved_tipo)

    stmt = select(Documento).where(Documento.id_siniestro == id_siniestro)
    existing_rows = list((await session.execute(stmt)).scalars().all())

    target: Documento | None = None
    for row in existing_rows:
        if row.tipo_documento.lower() == resolved_tipo.lower():
            target = row
            break
    if target is None:
        for row in existing_rows:
            if not row.entregado:
                target = row
                resolved_tipo = row.tipo_documento
                break

    sin = await session.get(Siniestro, id_siniestro)
    emission_date = sin.fecha_ocurrencia if sin is not None else date.today()

    if target is None:
        target = Documento(
            id_documento=f"{id_siniestro}-DOC-{uuid.uuid4().hex[:8].upper()}",
            id_siniestro=id_siniestro,
            tipo_documento=resolved_tipo,
        )
        session.add(target)

    target.tipo_documento = resolved_tipo
    target.entregado = True
    target.legible = True
    target.fecha_emision = emission_date
    target.storage_path = storage_path
    target.filename = filename
    target.content_type = content_type
    if not target.observacion or "Pendiente" in target.observacion:
        target.observacion = f"Recibido el {datetime.now(tz=UTC).date().isoformat()}."

    await session.flush()
    await refresh_documentos_completos(session, id_siniestro=id_siniestro)
    return target


async def refresh_documentos_completos(
    session: AsyncSession,
    *,
    id_siniestro: str,
) -> None:
    """Recompute siniestro.documentos_completos from entregado flags."""
    sin = await session.get(Siniestro, id_siniestro)
    if sin is None:
        return

    stmt = select(Documento).where(Documento.id_siniestro == id_siniestro)
    docs = list((await session.execute(stmt)).scalars().all())
    if not docs:
        sin.documentos_completos = False
        return

    sin.documentos_completos = all(doc.entregado for doc in docs)
    await session.flush()


async def clear_document_storage(
    session: AsyncSession,
    *,
    id_siniestro: str,
    storage_path: str,
) -> None:
    """Mark the matching documento as pending after storage deletion."""
    stmt = select(Documento).where(
        Documento.id_siniestro == id_siniestro,
        Documento.storage_path == storage_path,
    )
    doc = (await session.execute(stmt)).scalars().first()
    if doc is None:
        return

    doc.entregado = False
    doc.legible = False
    doc.storage_path = None
    doc.filename = None
    doc.content_type = None
    doc.observacion = "Pendiente de entrega por parte del asegurado."
    await session.flush()
    await refresh_documentos_completos(session, id_siniestro=id_siniestro)
