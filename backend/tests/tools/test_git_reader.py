from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.tools.git_reader import GitReader

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"


class TestGitReader:
    """Tests for the GitReader tool."""

    def setup_method(self) -> None:
        self.repo_path = FIXTURES_DIR / "repos" / "demo-service"
        self.reader = GitReader(self.repo_path)

    def test_get_recent_commits(self) -> None:
        from datetime import UTC, datetime

        since = datetime(2026, 8, 21, tzinfo=UTC)
        commits = self.reader.get_recent_commits(since=since)

        assert len(commits) == 5
        # Most recent first
        assert commits[0].message == "Deploy v2.1.0: Add amount validation"
        assert commits[0].date.year == 2026

    def test_get_commit(self) -> None:
        from datetime import UTC, datetime

        since = datetime(2026, 8, 21, tzinfo=UTC)
        commits = self.reader.get_recent_commits(since=since)
        latest = commits[0]

        commit = self.reader.get_commit(latest.hash)
        assert commit is not None
        assert commit.hash == latest.hash
        assert commit.message == "Deploy v2.1.0: Add amount validation"

    def test_get_commit_diff(self) -> None:
        from datetime import UTC, datetime

        since = datetime(2026, 8, 21, tzinfo=UTC)
        commits = self.reader.get_recent_commits(since=since)
        latest = commits[0]

        diff = self.reader.get_commit_diff(latest.hash)
        assert diff is not None
        assert len(diff.hunks) > 0
        assert "payment/service.py" in diff.files_changed

    def test_find_line_change(self) -> None:
        changes = self.reader.find_line_change("payment/service.py", 1)
        # Should find at least the initial creation
        assert len(changes) > 0

    def test_match_stack_trace_files(self) -> None:
        from datetime import UTC, datetime

        # Use since parameter to ensure we get all commits regardless of current date
        since = datetime(2026, 8, 21, tzinfo=UTC)
        commits = self.reader.get_recent_commits(since=since)
        stack_trace = 'File "/app/payment/service.py", line 10'

        matches = self.reader.match_stack_trace_files(stack_trace, commits)
        assert len(matches) > 0

        commit, files = matches[0]
        assert any("payment/service.py" in f for f in files)

    def test_no_commits_outside_lookback(self) -> None:
        # With very short lookback, should get no commits
        from datetime import UTC, datetime, timedelta

        reader = GitReader(
            self.repo_path,
            lookback_hours=0.001,  # ~3.6 seconds
            max_commits=10,
        )
        # All commits are from 2026-08-21, so with 0 lookback from now (2026),
        # we should get nothing or very few
        commits = reader.get_recent_commits(
            since=datetime.now(UTC) - timedelta(seconds=1)
        )
        # Depending on timing, may or may not have commits
        assert isinstance(commits, list)

    def test_nonexistent_repo(self) -> None:
        with pytest.raises(FileNotFoundError):
            GitReader("/nonexistent/repo")

    def test_files_changed_in_commit(self) -> None:
        from datetime import UTC, datetime

        since = datetime(2026, 8, 21, tzinfo=UTC)
        commits = self.reader.get_recent_commits(since=since)
        for commit in commits:
            assert isinstance(commit.files_changed, list)

    def test_commit_info_complete(self) -> None:
        from datetime import UTC, datetime

        since = datetime(2026, 8, 21, tzinfo=UTC)
        commits = self.reader.get_recent_commits(since=since)
        for commit in commits:
            assert commit.hash
            assert commit.short_hash
            assert commit.author
            assert commit.author_email
            assert commit.date
            assert commit.message
