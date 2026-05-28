"""0007_road_coords — recompute siniestro map coords on highway polylines.

Revision ID: 0007_road_coords
Revises: 0006_asegurado_nombre
Create Date: 2026-05-28

Vehicle claims now snap to simplified road segments instead of random city
jitter (which put coastal points in the ocean). Re-backfill every row.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.city_coords import coords_for_claim

revision: str = "0007_road_coords"
down_revision: str | None = "0006_asegurado_nombre"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id_siniestro, sucursal, ramo FROM siniestros WHERE sucursal IS NOT NULL")
    ).all()

    update = sa.text(
        "UPDATE siniestros SET latitude = :lat, longitude = :lng WHERE id_siniestro = :id"
    )
    for row in rows:
        coords = coords_for_claim(row.id_siniestro, row.sucursal or "", ramo=row.ramo)
        if coords is None:
            continue
        bind.execute(update, {"lat": coords[0], "lng": coords[1], "id": row.id_siniestro})


def downgrade() -> None:
    pass
