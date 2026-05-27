"""Use case: extended rule catalog with runtime state.

Combines `domain.rules.catalog.all_meta()` with:
- `kind`: derived from rule prefix (RF-01..04 → critica, RF-05..07 → amarilla, FS-* → scored).
- `activaciones_30d`: count of rule activations in the last 30 days from `claim_scores`.
- `enabled`: defaults to True (no runtime rule-toggle store yet).

Counts come from the `claim_scores.activations` JSONB array. Each activation entry
has a `code` field; we count rows whose array contains an element matching the rule code.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.rules.catalog import all_meta
from app.domain.rules.ports import RuleMeta
from app.infrastructure.db.models.claim_score import ClaimScore
from app.schemas.rules_config import RuleConfigOut, RuleKind

_CRITICAL_RF_CODES = {"RF-01", "RF-02", "RF-03", "RF-04"}
_YELLOW_RF_CODES = {"RF-05", "RF-06", "RF-07"}

_DISABLED_BY_DEFAULT: set[str] = {"FS-14"}


def _kind_for(code: str) -> RuleKind:
    if code in _CRITICAL_RF_CODES:
        return RuleKind.critica
    if code in _YELLOW_RF_CODES:
        return RuleKind.amarilla
    return RuleKind.scored


async def _activations_in_window(
    session: AsyncSession,
    code: str,
    *,
    since: datetime,
) -> int:
    """Count claim_scores rows whose `activations` JSONB contains an entry with this code."""
    query = (
        select(func.count())
        .select_from(ClaimScore)
        .where(
            ClaimScore.computed_at >= since,
            ClaimScore.activations.contains([{"code": code}]),
        )
    )
    result = (await session.execute(query)).scalar()
    return int(result or 0)


def _project(meta: RuleMeta, *, activaciones_30d: int) -> RuleConfigOut:
    return RuleConfigOut(
        code=meta.code,
        titulo=meta.name,
        descripcion=meta.short_description,
        clasificacion=meta.tier_hint,
        kind=_kind_for(meta.code),
        max_pts=meta.max_points,
        activaciones_30d=activaciones_30d,
        enabled=meta.code not in _DISABLED_BY_DEFAULT,
    )


async def list_rules_config(session: AsyncSession | None) -> list[RuleConfigOut]:
    metas = all_meta()
    if session is None:
        return [_project(m, activaciones_30d=0) for m in metas]

    since = datetime.now(tz=timezone.utc) - timedelta(days=30)
    out: list[RuleConfigOut] = []
    for meta in metas:
        try:
            count = await _activations_in_window(session, meta.code, since=since)
        except Exception:
            count = 0
        out.append(_project(meta, activaciones_30d=count))
    return out
