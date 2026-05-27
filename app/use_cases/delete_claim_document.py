"""Delete a document for a given claim (siniestro).

Validates that the path belongs to the claim before deletion to prevent
cross-claim file removal.  Rejects any path that does not start with
``{id_siniestro}/`` by raising ValidationFailed (422).
"""

from __future__ import annotations

from app.core.config import settings
from app.core.errors import ValidationFailed
from app.infrastructure.storage.ports import Storage


async def delete_claim_document(
    *,
    storage: Storage,
    id_siniestro: str,
    path: str,
) -> None:
    """Validate ownership and delete the stored document.

    Args:
        storage: The configured storage adapter.
        id_siniestro: Claim ID — the path must be scoped to this claim.
        path: Relative path within the bucket (as returned by the upload endpoint).
    """
    # Reject paths that don't belong to this claim
    if not path.startswith(f"{id_siniestro}/"):
        raise ValidationFailed(
            f"La ruta proporcionada no pertenece al siniestro {id_siniestro!r}."
        )

    key = f"{settings.SUPABASE_STORAGE_BUCKET}/{path}"
    await storage.delete(key=key)
