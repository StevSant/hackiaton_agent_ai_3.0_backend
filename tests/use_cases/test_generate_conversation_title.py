from pathlib import Path

import pytest

from app.infrastructure.llm.fake_llm import InMemoryFakeLLM
from app.infrastructure.llm.prompt_loader import PromptLoader
from app.use_cases.conversations.generate_conversation_title import (
    GenerateConversationTitle,
    _fallback,
    _sanitize,
)

pytestmark = pytest.mark.asyncio


def test_sanitize_strips_quotes_and_trailing_punct():
    assert _sanitize('  "Top proveedores sospechosos."  ') == "Top proveedores sospechosos"


def test_fallback_uses_first_line_of_query():
    assert _fallback("¿Qué proveedores son sospechosos?\nMás detalles") == "¿Qué proveedores son sospechosos?"


async def test_generate_uses_llm_response(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "conversation_title.v1.md").write_text(
        "Q: {query} A: {answer}", encoding="utf-8"
    )

    # InMemoryFakeLLM uses `script=` (a dict of query-substring → response).
    # The filled prompt will contain the query text, so we key on a substring of it.
    llm = InMemoryFakeLLM(script={"proveedores": "Proveedores reincidentes\n"})
    uc = GenerateConversationTitle(
        llm=llm,
        prompts=PromptLoader(base_dir=prompts_dir),
        model="fake",
    )
    title = await uc.execute("¿Qué proveedores?", "Los siguientes proveedores destacan...")
    assert title == "Proveedores reincidentes"
