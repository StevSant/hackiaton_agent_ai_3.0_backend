"""Use case: extended rule catalog with runtime state.

Combines `domain.rules.catalog.all_meta()` with:
- `kind`: derived from rule prefix (RF-01..04 → critica, RF-05..07 → amarilla, FS-* → scored).
- `activaciones_30d`: count of rule activations in the last 30 days from `claim_scores`.
- `enabled`: read from the runtime loader (hydrated from `rule_overrides` at startup).
- `thresholds`: the rule's effective numeric thresholds (defaults ⊕ overrides).

Counts come from the `claim_scores.activations` JSONB array. Each activation entry
has a `code` field; we run ONE GROUP BY query to bucket all activations by code,
then project. (Previously this fired 21 sequential count queries — one per rule.)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.rules.catalog import all_meta
from app.domain.rules.loader import numeric_thresholds, rule_enabled
from app.domain.rules.ports import RuleMeta
from app.schemas.rules_config import RuleConfigOut, RuleKind

_CRITICAL_RF_CODES = {"RF-01", "RF-02", "RF-03", "RF-04"}
_YELLOW_RF_CODES = {"RF-05", "RF-06", "RF-07"}


def _kind_for(code: str) -> RuleKind:
    if code in _CRITICAL_RF_CODES:
        return RuleKind.critica
    if code in _YELLOW_RF_CODES:
        return RuleKind.amarilla
    return RuleKind.scored


def _config_key(code: str) -> str:
    """Map a rule code (``FS-01``) to its config.yaml key (``FS_01``)."""
    return code.replace("-", "_")


async def _activation_counts_by_code(
    session: AsyncSession, *, since: datetime
) -> dict[str, int]:
    """One SQL: bucket every recent activation by rule code.

    Uses ``CROSS JOIN LATERAL jsonb_array_elements`` to unnest the JSONB array
    of activations on each claim_scores row, then groups by ``code``.
    Returns a mapping from rule code to count; rules with zero activations are
    simply absent from the map.
    """
    stmt = text(
        """
        SELECT act->>'code' AS code, COUNT(*) AS cnt
        FROM claim_scores cs
        CROSS JOIN LATERAL jsonb_array_elements(cs.activations) AS act
        WHERE cs.computed_at >= :since
        GROUP BY act->>'code'
        """
    )
    result = await session.execute(stmt, {"since": since})
    return {row.code: int(row.cnt) for row in result if row.code}


def _project(meta: RuleMeta, *, activaciones_30d: int) -> RuleConfigOut:
    return RuleConfigOut(
        code=meta.code,
        titulo=meta.name,
        descripcion=meta.short_description,
        clasificacion=meta.tier_hint,
        kind=_kind_for(meta.code),
        max_pts=meta.max_points,
        activaciones_30d=activaciones_30d,
        enabled=rule_enabled(meta.code),
        thresholds=numeric_thresholds(_config_key(meta.code)),
    )


async def list_rules_config(session: AsyncSession | None) -> list[RuleConfigOut]:
    metas = all_meta()
    if session is None:
        return [_project(m, activaciones_30d=0) for m in metas]

    since = datetime.now(tz=UTC) - timedelta(days=30)
    try:
        counts = await _activation_counts_by_code(session, since=since)
    except Exception:
        counts = {}
    return [_project(m, activaciones_30d=counts.get(m.code, 0)) for m in metas]
