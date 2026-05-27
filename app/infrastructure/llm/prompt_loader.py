"""Versioned prompt loader. Loads `app/agents/<graph>/prompts/<name>.v<n>.md`.

Prompts are stored as files, never inlined in node code (root CLAUDE.md §11, anti-pattern
"Inline prompts > 5 lines"). Versioning lets us evolve prompts without breaking callers
that pin the old version.
"""

from functools import lru_cache
from pathlib import Path


class PromptLoader:
    """Loads prompts from disk; caches results so each prompt is read once per process."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    @lru_cache(maxsize=64)  # noqa: B019 — instance-bound; loader lives for app lifetime
    def load(self, name: str, version: str = "v1") -> str:
        path = self._base_dir / f"{name}.{version}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt not found: {path}")
        return path.read_text(encoding="utf-8")
