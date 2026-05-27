"""0002_proveedor_nombre — add `nombre` column to `beneficiarios_proveedores`.

Revision ID: 0002_proveedor_nombre
Revises: 0001_initial
Create Date: 2026-05-27

Adds a human-readable display name for providers/beneficiaries. The original
ingest mapping slugified the readable name into the ID and discarded it, so
provider rows could not be rendered with a user-facing label. This column
backs the new ingest path that persists the name alongside the slug ID.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002_proveedor_nombre"
down_revision: str | None = "0001_initial"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "beneficiarios_proveedores",
        sa.Column("nombre", sa.String(160), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("beneficiarios_proveedores", "nombre")
