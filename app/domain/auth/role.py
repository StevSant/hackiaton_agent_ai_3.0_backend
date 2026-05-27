from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Roles available in V0. Do not add new roles without updating the spec §6 / §13 / §10."""

    analista = "analista"
    antifraude = "antifraude"
