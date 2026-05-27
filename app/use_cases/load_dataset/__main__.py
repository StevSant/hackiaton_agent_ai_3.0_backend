"""CLI entry point: `uv run python -m app.use_cases.load_dataset`."""

from __future__ import annotations

import asyncio

from app.use_cases.load_dataset.loader import _main

if __name__ == "__main__":
    asyncio.run(_main())
