"""Cross-cutting auto-scope middleware for agent tool calls.

When a chat session has a focused entity (claim, provider, or asegurado) the
dispatcher injects the appropriate id into tool args so the analyst doesn't have
to type it explicitly.

Rules per focus kind:
  - Claim focus (`focus_claim_id`):
      - `get_claim_detail` → injects `claim_id` unconditionally (unless LLM gave one).
      - Broad tools (`query_claims`, `aggregate_by_dimension`, `missing_documents`,
        `summarize_critical`) → injects `filter_claim_id` ONLY when the user's
        phrasing contains "este caso / el caso / este siniestro".
  - Provider focus (`focus_provider_id`):
      - `get_provider_detail` → injects `provider_id` unconditionally.
      - Broad tools → injects `filter_provider_id` ONLY when phrasing matches
        "este proveedor / ese proveedor / el proveedor / este beneficiario /
        ese beneficiario / el beneficiario".
  - Asegurado focus (`focus_asegurado_id`):
      - `get_asegurado_detail` → injects `asegurado_id` unconditionally.
      - Broad tools → injects `filter_asegurado_id` ONLY when phrasing matches
        "este asegurado / ese asegurado / el asegurado / este cliente /
        ese cliente / el cliente".

The "scope only when phrasing matches" rule for broad tools preserves Q3
("qué proveedores concentran más alertas?") behavior: even pinned to
provider P-0042 that question must still return the full ranking.

SINGLE RESPONSIBILITY: this module owns the injection heuristic. No tool
file needs to know about focus context.

Public API
----------
FocusContext                        — value object (at most one id set)
inject_focus_context(args, tool_name, focus, user_message) -> dict
inject_focus_claim_id(...)          — legacy alias kept for existing callers
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns — focused-entity phrasing detection
# ---------------------------------------------------------------------------

_FOCUSED_QUESTION_RE = re.compile(
    r"\b(este|ese|el)\s+(caso|siniestro)\b",
    re.IGNORECASE,
)

_FOCUSED_PROVIDER_RE = re.compile(
    r"\b(este|ese|el)\s+(proveedor|beneficiario)\b",
    re.IGNORECASE,
)

_FOCUSED_ASEGURADO_RE = re.compile(
    r"\b(este|ese|el)\s+(asegurado|cliente)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Tool routing tables
# ---------------------------------------------------------------------------

# Tools with a mandatory entity-id param — inject unconditionally (no phrasing gate).
_CLAIM_ID_TOOLS: frozenset[str] = frozenset({"get_claim_detail"})
_PROVIDER_ID_TOOLS: frozenset[str] = frozenset({"get_provider_detail"})
_ASEGURADO_ID_TOOLS: frozenset[str] = frozenset({"get_asegurado_detail"})

# Broad tools that accept optional filter params — inject ONLY when phrasing matches.
_FILTER_CLAIM_ID_TOOLS: frozenset[str] = frozenset(
    {
        "query_claims",
        "aggregate_by_dimension",
        "missing_documents",
        "summarize_critical",
    }
)
_FILTER_PROVIDER_ID_TOOLS: frozenset[str] = _FILTER_CLAIM_ID_TOOLS
_FILTER_ASEGURADO_ID_TOOLS: frozenset[str] = _FILTER_CLAIM_ID_TOOLS


# ---------------------------------------------------------------------------
# FocusContext value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FocusContext:
    """Tagged union: at most one entity focus per agent session.

    Mirrors the single-focus invariant enforced by the wire schema validator.
    """

    claim_id: str | None = None
    provider_id: str | None = None
    asegurado_id: str | None = None

    def __post_init__(self) -> None:
        set_count = sum(
            v is not None for v in (self.claim_id, self.provider_id, self.asegurado_id)
        )
        if set_count > 1:
            raise ValueError(
                "FocusContext: at most one of claim_id / provider_id / asegurado_id may be set"
            )

    @property
    def is_empty(self) -> bool:
        return (
            self.claim_id is None
            and self.provider_id is None
            and self.asegurado_id is None
        )


# ---------------------------------------------------------------------------
# Phrasing helpers
# ---------------------------------------------------------------------------


def _is_focused_claim_question(message: str) -> bool:
    return bool(_FOCUSED_QUESTION_RE.search(message))


def _is_focused_provider_question(message: str) -> bool:
    return bool(_FOCUSED_PROVIDER_RE.search(message))


def _is_focused_asegurado_question(message: str) -> bool:
    return bool(_FOCUSED_ASEGURADO_RE.search(message))


# ---------------------------------------------------------------------------
# Main injection function
# ---------------------------------------------------------------------------


def inject_focus_context(
    *,
    tool_name: str,
    llm_args: dict[str, Any],
    focus: FocusContext,
    last_user_message: str,
) -> dict[str, Any]:
    """Return a (possibly enriched) copy of `llm_args` with the focus injected.

    Called by ToolEntry.run_with_context for every tool dispatch.
    """
    if focus.is_empty:
        return dict(llm_args)

    args = dict(llm_args)

    # ---- Claim focus -------------------------------------------------------
    if focus.claim_id:
        if tool_name in _CLAIM_ID_TOOLS:
            if not args.get("claim_id"):
                args["claim_id"] = focus.claim_id
        elif tool_name in _FILTER_CLAIM_ID_TOOLS:
            if not args.get("filter_claim_id") and _is_focused_claim_question(
                last_user_message
            ):
                args["filter_claim_id"] = focus.claim_id

    # ---- Provider focus ----------------------------------------------------
    if focus.provider_id:
        if tool_name in _PROVIDER_ID_TOOLS:
            if not args.get("provider_id"):
                args["provider_id"] = focus.provider_id
        elif tool_name in _FILTER_PROVIDER_ID_TOOLS:
            if not args.get("filter_provider_id") and _is_focused_provider_question(
                last_user_message
            ):
                args["filter_provider_id"] = focus.provider_id

    # ---- Asegurado focus ---------------------------------------------------
    if focus.asegurado_id:
        if tool_name in _ASEGURADO_ID_TOOLS:
            if not args.get("asegurado_id"):
                args["asegurado_id"] = focus.asegurado_id
        elif tool_name in _FILTER_ASEGURADO_ID_TOOLS:
            if not args.get("filter_asegurado_id") and _is_focused_asegurado_question(
                last_user_message
            ):
                args["filter_asegurado_id"] = focus.asegurado_id

    return args


# ---------------------------------------------------------------------------
# Legacy alias — keeps existing callers (test_focus_claim_id.py) green
# ---------------------------------------------------------------------------


def inject_focus_claim_id(
    *,
    tool_name: str,
    llm_args: dict[str, Any],
    focus_claim_id: str | None,
    last_user_message: str,
) -> dict[str, Any]:
    """Backward-compatible wrapper around inject_focus_context."""
    focus = FocusContext(claim_id=focus_claim_id)
    return inject_focus_context(
        tool_name=tool_name,
        llm_args=llm_args,
        focus=focus,
        last_user_message=last_user_message,
    )
