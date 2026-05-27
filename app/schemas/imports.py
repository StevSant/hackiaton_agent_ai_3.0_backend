"""Import endpoint schema — response contract for POST /claims/import."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImportResult(BaseModel):
    """Summary returned after a bulk-import operation.

    * imported — rows successfully upserted (score computed + all tables written).
    * skipped  — rows skipped due to non-fatal parse/validation errors.
    * errors   — per-row human-readable error messages (one per skipped row).
    * claim_ids — IDs of successfully imported claims (for document upload step).
    """

    imported: int
    skipped: int
    errors: list[str]
    claim_ids: list[str] = Field(default_factory=list)
