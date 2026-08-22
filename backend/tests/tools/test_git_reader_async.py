"""Tests for the off-loop GitReader wrappers.

The agents run inside the event loop, so ``subprocess.run`` must not execute
there: a slow ``git log`` would stall every other request on the server.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from pathlib import Path

from backend.app.tools.git_reader import GitReader

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"
SINCE = datetime(2026, 8, 21, tzinfo=UTC)


class TestGitReaderAsync:
    """The ``*_async`` wrappers must match the sync results exactly."""

    def setup_method(self) -> None:
        self.repo_path = FIXTURES_DIR / "repos" / "demo-service"
        self.reader = GitReader(self.repo_path)

    async def test_get_recent_commits_async_matches_sync(self) -> None:
        expected = self.reader.get_recent_commits(since=SINCE)
        actual = await self.reader.get_recent_commits_async(since=SINCE)

        assert actual == expected
        assert [c.hash for c in actual] == [c.hash for c in expected]
        assert [c.files_changed for c in actual] == [c.files_changed for c in expected]

    async def test_get_commit_async_matches_sync(self) -> None:
        latest = self.reader.get_recent_commits(since=SINCE)[0]

        assert await self.reader.get_commit_async(latest.hash) == self.reader.get_commit(
            latest.hash
        )

    async def test_get_commit_async_returns_none_for_unknown_hash(self) -> None:
        assert await self.reader.get_commit_async("0" * 40) is None

    async def test_get_commit_diff_async_matches_sync(self) -> None:
        latest = self.reader.get_recent_commits(since=SINCE)[0]

        expected = self.reader.get_commit_diff(latest.hash)
        actual = await self.reader.get_commit_diff_async(latest.hash)

        assert actual == expected
        assert actual is not None
        assert actual.commit_hash == latest.hash

    async def test_find_line_change_async_matches_sync(self) -> None:
        expected = self.reader.find_line_change("README.md", 1, lookback_commits=5)
        actual = await self.reader.find_line_change_async("README.md", 1, lookback_commits=5)

        assert actual == expected

    async def test_max_count_is_forwarded(self) -> None:
        commits = await self.reader.get_recent_commits_async(since=SINCE, max_count=2)

        assert len(commits) == 2


class TestGitReaderDoesNotBlockEventLoop:
    """Deterministic proof that git never runs on the event loop thread."""

    def setup_method(self) -> None:
        self.reader = GitReader(FIXTURES_DIR / "repos" / "demo-service")

    async def test_subprocess_runs_off_the_event_loop_thread(self) -> None:
        loop_thread_id = threading.get_ident()
        observed: list[int] = []
        original = GitReader._run_git

        def spy(reader: GitReader, *args: str) -> str:
            observed.append(threading.get_ident())
            return original(reader, *args)

        GitReader._run_git = spy  # type: ignore[method-assign]
        try:
            await self.reader.get_recent_commits_async(since=SINCE)
            await self.reader.get_commit_diff_async("HEAD")
        finally:
            GitReader._run_git = original  # type: ignore[method-assign]

        assert observed, "expected at least one git invocation"
        assert loop_thread_id not in observed

    async def test_event_loop_stays_responsive_during_git_work(self) -> None:
        """Other coroutines must keep making progress while git runs."""
        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0)

        pump = asyncio.create_task(ticker())
        try:
            # Enough git work to be measurable: 5 commits, each shelling out.
            await self.reader.get_recent_commits_async(since=SINCE)
        finally:
            pump.cancel()

        assert ticks > 0
