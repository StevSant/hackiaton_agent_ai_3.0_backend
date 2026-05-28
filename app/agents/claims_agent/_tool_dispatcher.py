"""Cross-cutting auto-scope middleware for agent tool calls.

When a chat session has a focused case (`focus_claim_id` in the UI context),
tool args should be scoped to that case unless:
  - the LLM already provided an explicit claim id (user asked about a
    different claim), OR
  - the tool is `aggregate_by_dimension` and the question is broad (no
    "este caso / el caso / este siniestro" phrasing).

SINGLE RESPONSIBILITY: this module owns the injection heuristic. No tool
file needs to know about focus_claim_id.

Public API
----------
inject_focus_claim_id(tool_name, llm_args, focus_claim_id, last_user_message)
    -> dict[str, object]   — possibly enriched copy of llm_args
"""

from __future__ import annotations

import re
from typing import Any

# Regex that detects "focused-case" phrasing in the user's question.
# Matches: "este caso", "el caso", "este siniestro", "ese caso", "ese siniestro".
_FOCUSED_QUESTION_RE = re.compile(
    r"\b(este|ese|el)\s+(caso|siniestro)\b",
    re.IGNORECASE,
)

# Tools that carry an explicit `claim_id` parameter.
# Injection: if LLM omitted claim_id and focus is set → inject it.
_CLAIM_ID_TOOLS: frozenset[str] = frozenset({"get_claim_detail"})

# Tools that accept an optional `filter_claim_id` parameter (broad by nature;
# inject ONLY when the user's phrasing is case-focused).
_FILTER_CLAIM_ID_TOOLS: frozenset[str] = frozenset(
    {
        "query_claims",
        "aggregate_by_dimension",
        "missing_documents",
        "summarize_critical",
    }
)


def _is_focused_question(message: str) -> bool:
    """Return True when the user's question is scoped to a specific case."""
    return bool(_FOCUSED_QUESTION_RE.search(message))


def inject_focus_claim_id(
    *,
    tool_name: str,
    llm_args: dict[str, Any],
    focus_claim_id: str | None,
    last_user_message: str,
) -> dict[str, Any]:
    """Return a (possibly enriched) copy of `llm_args` with the focus injected.

    Rules:
    - If `focus_claim_id` is None → return llm_args unchanged.
    - For tools in `_CLAIM_ID_TOOLS` (e.g. get_claim_detail):
        - If LLM already provided `claim_id` → keep LLM's value.
        - Otherwise → inject focus as `claim_id`.
    - For tools in `_FILTER_CLAIM_ID_TOOLS` (broad aggregations etc.):
        - If LLM already provided `filter_claim_id` → keep it.
        - Inject focus as `filter_claim_id` ONLY when the user's question
          contains "este caso / el caso / este siniestro" phrasing.
        - Otherwise → leave unscoped (broad question, broad answer).
    - For unknown tools → pass args through unchanged.
    """
    if not focus_claim_id:
        return dict(llm_args)

    args = dict(llm_args)

    if tool_name in _CLAIM_ID_TOOLS:
        if not args.get("claim_id"):
            args["claim_id"] = focus_claim_id

    elif tool_name in _FILTER_CLAIM_ID_TOOLS:
        if not args.get("filter_claim_id") and _is_focused_question(last_user_message):
            args["filter_claim_id"] = focus_claim_id

    return args
