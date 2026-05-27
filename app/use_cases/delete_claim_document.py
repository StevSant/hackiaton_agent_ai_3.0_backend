"""Delete a document for a given claim (siniestro)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFound, ValidationFailed
from app.infrastructure.db.models.siniestro import Siniestro
from app.infrastructure.storage.ports import Storage
from app.use_cases.sync_claim_document import clear_document_storage


def _can_access_claim(sin: Siniestro | None, workspace_id: UUID | None) -> bool:
    if sin is None:
        return False
    if workspace_id is None:
        return True
    return sin.workspace_id is None or sin.workspace_id == workspace_id


async def delete_claim_document(
    *,
    session: AsyncSession,
    storage: Storage,
    id_siniestro: str,
    path: str,
    workspace_id: UUID | None = None,
) -> None:
    """Validate ownership, delete storage object, and mark documento pending."""
    sin = await session.get(Siniestro, id_siniestro)
    if not _can_access_claim(sin, workspace_id):
        raise NotFound(f"Siniestro {id_siniestro!r} no encontrado")

    if not path.startswith(f"{id_siniestro}/"):
        raise ValidationFailed(
            f"La ruta proporcionada no pertenece al siniestro {id_siniestro!r}."
        )

    key = f"{settings.SUPABASE_STORAGE_BUCKET}/{path}"
    await storage.delete(key=key)
    await clear_document_storage(
        session,
        id_siniestro=id_siniestro,
        storage_path=path,
    )
    await session.commit()
