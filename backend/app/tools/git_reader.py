from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class CommitInfo:
    """Structured information about a git commit."""

    hash: str
    short_hash: str
    author: str
    author_email: str
    date: datetime
    message: str
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


@dataclass
class DiffHunk:
    """A hunk from a git diff."""

    file_path: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str


@dataclass
class CommitDiff:
    """Full diff for a commit."""

    commit_hash: str
    hunks: list[DiffHunk] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)


@dataclass
class LineChange:
    """A specific line change in a commit."""

    commit_hash: str
    file_path: str
    line_number: int
    content: str
    change_type: str  # "added" or "removed"


class GitReader:
    """Deterministic git repository reader.

    Uses the git CLI to extract structured information.
    Does NOT allow arbitrary command execution.

    Every method that shells out to git has an ``*_async`` counterpart that runs
    the identical code in a worker thread. Async callers must use those: a
    ``git log`` over a large repository blocks ``subprocess.run`` for seconds,
    which would stall the event loop and every concurrent request with it.
    """

    def __init__(
        self,
        repo_path: str | Path,
        lookback_hours: float | None = None,
        max_commits: int | None = None,
    ) -> None:
        self._repo_path = Path(repo_path)
        if not self._repo_path.exists():
            raise FileNotFoundError(f"Git repository not found: {self._repo_path}")

        self._lookback_hours = float(
            os.getenv("GIT_LOOKBACK_HOURS", "24")
            if lookback_hours is None
            else lookback_hours
        )
        self._max_commits = int(
            os.getenv("GIT_MAX_COMMITS", "50")
            if max_commits is None
            else max_commits
        )

    def _run_git(self, *args: str) -> str:
        """Execute a git command safely."""
        cmd = ["git", "-C", str(self._repo_path)] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git command failed: {' '.join(cmd)}\n{result.stderr}"
            )
        return result.stdout

    def get_recent_commits(
        self,
        since: datetime | None = None,
        max_count: int | None = None,
    ) -> list[CommitInfo]:
        """Get recent commits within the lookback window."""
        count = max_count or self._max_commits
        since_str = ""
        if since:
            since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            # Calculate lookback from now
            from datetime import timedelta

            lookback = datetime.now(UTC) - timedelta(hours=self._lookback_hours)
            since_str = lookback.strftime("%Y-%m-%dT%H:%M:%S")

        format_str = "%H|%h|%an|%ae|%aI|%s"
        output = self._run_git(
            "log",
            f"--since={since_str}",
            f"--max-count={count}",
            f"--format={format_str}",
        )

        commits: list[CommitInfo] = []
        for line in output.strip().splitlines():
            if not line:
                continue
            parts = line.split("|", 5)
            if len(parts) < 6:
                continue

            hash_val, short_hash, author, email, date_str, message = parts
            try:
                date = datetime.fromisoformat(date_str)
            except ValueError:
                continue

            # Get files changed for this commit
            files = self._get_files_changed(hash_val.strip())

            commits.append(
                CommitInfo(
                    hash=hash_val.strip(),
                    short_hash=short_hash.strip(),
                    author=author.strip(),
                    author_email=email.strip(),
                    date=date,
                    message=message.strip(),
                    files_changed=files,
                )
            )

        return commits

    async def get_recent_commits_async(
        self,
        since: datetime | None = None,
        max_count: int | None = None,
    ) -> list[CommitInfo]:
        """Off-loop variant of :meth:`get_recent_commits`.

        One ``to_thread`` hop covers the whole method, including the per-commit
        ``git diff-tree`` calls, rather than one hop per subprocess.
        """
        return await asyncio.to_thread(self.get_recent_commits, since, max_count)

    def get_commit(self, commit_hash: str) -> CommitInfo | None:
        """Get a specific commit."""
        format_str = "%H|%h|%an|%ae|%aI|%s"
        try:
            output = self._run_git(
                "log", "-1", f"--format={format_str}", commit_hash
            )
        except RuntimeError:
            return None

        line = output.strip()
        if not line:
            return None

        parts = line.split("|", 5)
        if len(parts) < 6:
            return None

        hash_val, short_hash, author, email, date_str, message = parts
        try:
            date = datetime.fromisoformat(date_str)
        except ValueError:
            return None

        files = self._get_files_changed(hash_val.strip())

        return CommitInfo(
            hash=hash_val.strip(),
            short_hash=short_hash.strip(),
            author=author.strip(),
            author_email=email.strip(),
            date=date,
            message=message.strip(),
            files_changed=files,
        )

    async def get_commit_async(self, commit_hash: str) -> CommitInfo | None:
        """Off-loop variant of :meth:`get_commit`."""
        return await asyncio.to_thread(self.get_commit, commit_hash)

    def get_commit_diff(self, commit_hash: str) -> CommitDiff | None:
        """Get the diff for a specific commit."""
        try:
            output = self._run_git("diff", f"{commit_hash}~1..{commit_hash}")
        except RuntimeError:
            # Try the initial commit
            try:
                output = self._run_git("diff-tree", "--root", "-p", commit_hash)
            except RuntimeError:
                return None

        hunks: list[DiffHunk] = []
        files_changed: list[str] = []
        current_file = ""
        current_hunk_lines: list[str] = []
        old_start = old_count = new_start = new_count = 0

        for line in output.splitlines():
            if line.startswith("diff --git"):
                # Save previous hunk
                if current_hunk_lines and current_file:
                    hunks.append(
                        DiffHunk(
                            file_path=current_file,
                            old_start=old_start,
                            old_count=old_count,
                            new_start=new_start,
                            new_count=new_count,
                            content="\n".join(current_hunk_lines),
                        )
                    )
                    current_hunk_lines = []

                # Extract file path
                parts = line.split(" b/", 1)
                if len(parts) == 2:
                    current_file = parts[1]
                    files_changed.append(current_file)

            elif line.startswith("@@"):
                # Save previous hunk
                if current_hunk_lines and current_file:
                    hunks.append(
                        DiffHunk(
                            file_path=current_file,
                            old_start=old_start,
                            old_count=old_count,
                            new_start=new_start,
                            new_count=new_count,
                            content="\n".join(current_hunk_lines),
                        )
                    )
                    current_hunk_lines = []

                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                import re

                match = re.search(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2) or "1")
                    new_start = int(match.group(3))
                    new_count = int(match.group(4) or "1")
                current_hunk_lines.append(line)

            else:
                current_hunk_lines.append(line)

        # Save last hunk
        if current_hunk_lines and current_file:
            hunks.append(
                DiffHunk(
                    file_path=current_file,
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    content="\n".join(current_hunk_lines),
                )
            )

        return CommitDiff(
            commit_hash=commit_hash,
            hunks=hunks,
            files_changed=files_changed,
        )

    async def get_commit_diff_async(self, commit_hash: str) -> CommitDiff | None:
        """Off-loop variant of :meth:`get_commit_diff`."""
        return await asyncio.to_thread(self.get_commit_diff, commit_hash)

    def find_line_change(
        self, file_path: str, line_number: int, lookback_commits: int = 10
    ) -> list[LineChange]:
        """Find when a specific line was last changed."""
        output = self._run_git(
            "log",
            f"--max-count={lookback_commits}",
            "-L",
            f"{line_number},{line_number}:{file_path}",
            "--format=%H",
        )

        changes: list[LineChange] = []
        current_hash = ""

        for line in output.splitlines():
            if line.startswith("commit ") or (
                len(line) == 40 and all(c in "0123456789abcdef" for c in line)
            ):
                current_hash = line[:40]
            elif line.startswith("+") and not line.startswith("+++"):
                changes.append(
                    LineChange(
                        commit_hash=current_hash,
                        file_path=file_path,
                        line_number=line_number,
                        content=line[1:],
                        change_type="added",
                    )
                )
            elif line.startswith("-") and not line.startswith("---"):
                changes.append(
                    LineChange(
                        commit_hash=current_hash,
                        file_path=file_path,
                        line_number=line_number,
                        content=line[1:],
                        change_type="removed",
                    )
                )

        return changes

    async def find_line_change_async(
        self, file_path: str, line_number: int, lookback_commits: int = 10
    ) -> list[LineChange]:
        """Off-loop variant of :meth:`find_line_change`."""
        return await asyncio.to_thread(
            self.find_line_change, file_path, line_number, lookback_commits
        )

    def _get_files_changed(self, commit_hash: str) -> list[str]:
        """Get list of files changed in a commit."""
        try:
            output = self._run_git(
                "diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash
            )
            return [f for f in output.strip().splitlines() if f]
        except RuntimeError:
            return []

    def match_stack_trace_files(
        self, stack_trace: str, commits: list[CommitInfo]
    ) -> list[tuple[CommitInfo, list[str]]]:
        """Match stack trace file paths against changed files in commits.

        Returns commits that changed files referenced in the stack trace.
        """
        import re

        # Extract file paths from stack trace
        file_patterns = re.findall(
            r'(?:File\s+"|at\s+|/)([\w/\.\-]+\.(?:py|js|ts|java|go|rs))',
            stack_trace,
        )

        if not file_patterns:
            return []

        matches: list[tuple[CommitInfo, list[str]]] = []
        for commit in commits:
            matched_files: list[str] = []
            for pattern in file_patterns:
                # Extract just the filename portion for matching
                # e.g., /app/payment/service.py -> payment/service.py
                parts = pattern.split("/")
                # Try matching with decreasing path depth
                for depth in range(len(parts)):
                    candidate = "/".join(parts[depth:])
                    for changed_file in commit.files_changed:
                        if candidate in changed_file or changed_file.endswith(candidate):
                            matched_files.append(changed_file)
            if matched_files:
                matches.append((commit, list(set(matched_files))))

        return matches
