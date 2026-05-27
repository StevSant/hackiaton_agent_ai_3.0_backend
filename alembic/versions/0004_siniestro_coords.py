"""0004_siniestro_coords — add latitude/longitude to `siniestros` and backfill.

Revision ID: 0004_siniestro_coords
Revises: 0003_add_conversations
Create Date: 2026-05-27

Adds per-claim coordinates so the Insights map can plot each incident at a
specific point inside its sucursal's city. Existing rows are backfilled using
the same deterministic city-center + claim-id jitter the generator uses, so
re-running the generator does not change the spots of pre-existing rows.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.city_coords import coords_for_claim

revision: str = "0004_siniestro_coords"
down_revision: str | None = "0003_add_conversations"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("siniestros", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("siniestros", sa.Column("longitude", sa.Float(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id_siniestro, sucursal FROM siniestros WHERE sucursal IS NOT NULL")
    ).all()

    update = sa.text(
        "UPDATE siniestros SET latitude = :lat, longitude = :lng WHERE id_siniestro = :id"
    )
    for row in rows:
        coords = coords_for_claim(row.id_siniestro, row.sucursal or "")
        if coords is None:
            continue
        bind.execute(update, {"lat": coords[0], "lng": coords[1], "id": row.id_siniestro})


def downgrade() -> None:
    op.drop_column("siniestros", "longitude")
    op.drop_column("siniestros", "latitude")
