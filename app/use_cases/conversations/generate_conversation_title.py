"""Generate a short conversation title via the LLM. Falls back to a query truncation on failure."""

from __future__ import annotations

import logging
import re

from app.infrastructure.llm.ports import LLMProvider
from app.infrastructure.llm.prompt_loader import PromptLoader
from app.infrastructure.llm.types import Message

logger = logging.getLogger(__name__)


def _fallback(query: str) -> str:
    cleaned = query.strip().splitlines()[0] if query.strip() else "Conversación"
    return cleaned[:60]


def _sanitize(title: str) -> str:
    title = re.sub(r"^[\s\"'`]+|[\s\"'`.!?]+$", "", title).strip()
    return title[:120] if title else "Sin título"


class GenerateConversationTitle:
    def __init__(
        self,
        llm: LLMProvider,
        prompts: PromptLoader,
        model: str,
    ) -> None:
        self._llm = llm
        self._prompts = prompts
        self._model = model

    async def execute(self, query: str, answer: str) -> str:
        try:
            template = self._prompts.load("conversation_title", "v1")
            filled = template.replace("{query}", query[:500]).replace(
                "{answer}", answer[:1500]
            )
            result = await self._llm.complete(
                [Message(role="user", content=filled)],
                model=self._model,
            )
            return _sanitize(result.message.content)
        except Exception as exc:
            logger.warning("Title generation failed: %s", exc)
            return _fallback(query)
