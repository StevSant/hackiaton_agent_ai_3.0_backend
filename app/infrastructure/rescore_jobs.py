"""In-process background rescore job — at most one at a time, poll-friendly.

The rescore runs as a detached asyncio task with its OWN DB session, so no HTTP
request stays open while it walks the portfolio (a long-lived request is what
froze the app under uvicorn's graceful-shutdown drain). The dashboard polls
``GET /rules/rescore/status`` and renders the snapshot.

Single-process by design (hackathon): the snapshot lives in this module. If we
ever run multiple workers, this moves to a shared store (DB row / Redis).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

RescoreJobState = Literal["idle", "running", "done", "error"]

# A runner receives the on_progress callback and returns rescore_all's counts.
RescoreRunner = Callable[
    [Callable[[int, int, int], Awaitable[None]]], Awaitable[dict[str, int]]
]


@dataclass(frozen=True, slots=True)
class RescoreJobSnapshot:
    status: RescoreJobState
    processed: int = 0
    total: int = 0
    changed: int = 0
    error: str | None = None


class RescoreJobManager:
    """Owns the single background rescore task + its progress snapshot."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._snapshot = RescoreJobSnapshot(status="idle")

    def snapshot(self) -> RescoreJobSnapshot:
        return self._snapshot

    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, runner: RescoreRunner) -> bool:
        """Launch the job; returns False (no-op) when one is already running."""
        if self.running():
            return False
        self._snapshot = RescoreJobSnapshot(status="running")
        self._task = asyncio.create_task(self._run(runner), name="rescore-job")
        return True

    async def _run(self, runner: RescoreRunner) -> None:
        try:
            counts = await runner(self._on_progress)
            self._snapshot = RescoreJobSnapshot(
                status="done",
                processed=counts["processed"],
                total=counts["processed"],
                changed=counts["changed"],
            )
            logger.info("rescore job done: %s", self._snapshot)
        except Exception as exc:
            logger.exception("rescore job failed")
            self._snapshot = RescoreJobSnapshot(status="error", error=str(exc))

    async def _on_progress(self, processed: int, total: int, changed: int) -> None:
        self._snapshot = RescoreJobSnapshot(
            status="running", processed=processed, total=total, changed=changed
        )


# Module-level singleton (same pattern as engine.py's session factory); the
# route reaches it through api.deps.get_rescore_job_manager.
_manager = RescoreJobManager()


def get_rescore_job_manager() -> RescoreJobManager:
    return _manager
