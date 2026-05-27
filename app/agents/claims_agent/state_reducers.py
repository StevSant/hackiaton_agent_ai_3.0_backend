"""Reducers for the claims-agent state.

`_trim_to_last_n_turns` keeps the last N conversation turns intact in `messages`,
where one turn = HumanMessage + every following message until the next HumanMessage.
SystemMessages are always preserved at the head. Adapted from the Patrimore
financial-advisor agent — same problem (multi-turn chat) so same solution.

Why preserve whole turns: a ToolMessage without its parent AIMessage breaks the
LLM's tool-use protocol. Trimming mid-turn is worse than trimming none.
"""

from collections.abc import Sequence
from uuid import uuid4

from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage, SystemMessage

from app.core.config import settings


def trim_to_last_n_turns(
    existing: Sequence[BaseMessage], new: Sequence[BaseMessage]
) -> list[BaseMessage]:
    """LangGraph reducer: append `new` to `existing` then trim to last N turns.

    Mirrors `add_messages`' behavior for ID assignment + RemoveMessage handling,
    then applies the turn-windowing pass. `RemoveMessage` semantics: any id in
    `new` matching an `existing` id removes that message.
    """
    new_list = list(new)

    # Assign IDs to incoming messages without one (mirrors add_messages).
    new_list = [
        m.model_copy(update={"id": str(uuid4())})
        if not isinstance(m, RemoveMessage) and m.id is None
        else m
        for m in new_list
    ]

    # Process RemoveMessage signals: drop matching ids from `existing`.
    remove_ids = {m.id for m in new_list if isinstance(m, RemoveMessage) and m.id is not None}
    if remove_ids:
        existing = [m for m in existing if m.id not in remove_ids]
    new_list = [m for m in new_list if not isinstance(m, RemoveMessage)]

    combined = list(existing) + new_list

    system_msgs = [m for m in combined if isinstance(m, SystemMessage)]
    non_system = [m for m in combined if not isinstance(m, SystemMessage)]

    max_turns = settings.MAX_CONVERSATION_TURNS

    # Fast path: already under the limit.
    human_count = sum(1 for m in non_system if isinstance(m, HumanMessage))
    if human_count <= max_turns:
        return system_msgs + non_system

    # Slow path: group into turns, then keep the last N.
    turns: list[list[BaseMessage]] = []
    current: list[BaseMessage] = []
    for msg in non_system:
        if isinstance(msg, HumanMessage) and current:
            turns.append(current)
            current = [msg]
        else:
            current.append(msg)
    if current:
        turns.append(current)

    turns = turns[-max_turns:]
    return system_msgs + [msg for turn in turns for msg in turn]
