from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.models.agent_schemas import AgentResult
from backend.app.models.evidence import Evidence, SourceType
from backend.app.models.findings import AgentFinding, FindingType
from backend.app.repositories import EvidenceRepository, FindingRepository
from backend.app.tools.git_reader import GitReader


class GitForensicsAgent:
    """Deterministic git forensics agent.

    Inspects recent commits, identifies candidate changes that
    may be related to the incident, and produces structured findings.

    Uses language like "candidate_change" not "root_cause".
    RCA belongs to Phase 4.
    """

    name = "git_forensics"

    def __init__(
        self,
        evidence_repo: EvidenceRepository,
        finding_repo: FindingRepository,
        git_reader: GitReader | None = None,
    ) -> None:
        self._evidence_repo = evidence_repo
        self._finding_repo = finding_repo
        self._git_reader = git_reader

    async def run(self, context: InvestigationContext) -> AgentResult:
        """Analyze git history for the given incident."""
        incident_id = context.incident_id
        repo_path = context.extra.get("repo_path")

        if not repo_path:
            return AgentResult(
                agent_name=self.name,
                summary="No repository path provided in investigation context",
                confidence=0.0,
                metadata={"status": "no_input"},
            )

        if self._git_reader is None:
            try:
                self._git_reader = GitReader(repo_path)
            except FileNotFoundError:
                return AgentResult(
                    agent_name=self.name,
                    summary=f"Git repository not found: {repo_path}",
                    confidence=0.0,
                    metadata={"status": "repo_not_found", "path": repo_path},
                )

        try:
            recent_commits = self._git_reader.get_recent_commits()
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                summary=f"Failed to read git history: {e}",
                confidence=0.0,
                metadata={"status": "error", "error": str(e)},
            )

        if not recent_commits:
            return AgentResult(
                agent_name=self.name,
                summary="No recent commits found within lookback window",
                confidence=0.1,
                metadata={"status": "no_commits", "repo_path": repo_path},
            )

        # Create evidence for recent commits
        evidence_ids = []
        candidate_commits = []

        # Get stack trace from context for correlation
        stack_trace = context.extra.get("stack_trace", "")
        incident_service = context.extra.get("service", "")

        for commit in recent_commits[:20]:  # Limit to 20 commits
            # Create commit evidence
            commit_evidence = self._create_commit_evidence(
                incident_id, commit, repo_path
            )
            evidence_ids.append(commit_evidence["id"])

            # Get diff for this commit
            diff = self._git_reader.get_commit_diff(commit.hash)
            if diff and diff.hunks:
                diff_evidence = self._create_diff_evidence(
                    incident_id, commit, diff, repo_path
                )
                evidence_ids.append(diff_evidence["id"])

            # Check if this commit is a candidate change
            is_candidate = self._is_candidate_change(
                commit, stack_trace, incident_service
            )
            if is_candidate:
                candidate_commits.append(commit)

        # Build finding
        finding = self._build_finding(
            incident_id, candidate_commits, recent_commits, evidence_ids
        )

        return AgentResult(
            agent_name=self.name,
            summary=finding["summary"],
            findings=[{
                "finding_type": finding["finding_type"],
                "summary": finding["summary"],
                "confidence": finding["confidence"],
                "candidate_count": len(candidate_commits),
                "total_commits": len(recent_commits),
                "candidates": [
                    {
                        "hash": c.short_hash,
                        "message": c.message[:100],
                        "files": c.files_changed[:5],
                    }
                    for c in candidate_commits[:5]
                ],
            }],
            confidence=finding["confidence"],
            metadata={
                "evidence_ids": [str(eid) for eid in evidence_ids],
                "finding_id": str(finding["id"]),
                "repo_path": repo_path,
                "total_commits": len(recent_commits),
                "candidate_commits": len(candidate_commits),
            },
        )

    def _create_commit_evidence(
        self, incident_id: Any, commit: Any, repo_path: str
    ) -> Evidence:
        """Create evidence for a commit."""
        content = (
            f"Commit: {commit.hash}\n"
            f"Author: {commit.author} <{commit.author_email}>\n"
            f"Date: {commit.date.isoformat()}\n"
            f"Message: {commit.message}\n"
            f"Files changed: {', '.join(commit.files_changed)}"
        )

        evidence = Evidence(
            id=uuid4(),
            incident_id=incident_id,
            source_type=SourceType.GIT_COMMIT,
            source_reference=commit.hash,
            content=content,
            timestamp=commit.date,
            metadata={
                "commit_hash": commit.hash,
                "author": commit.author,
                "files_changed": commit.files_changed,
            },
        )

        return self._evidence_repo.create_evidence(
            id=evidence.id,
            incident_id=evidence.incident_id,
            source_type=evidence.source_type.value,
            source_reference=evidence.source_reference,
            content=evidence.content,
            timestamp=evidence.timestamp,
            metadata=evidence.metadata,
            created_at=evidence.created_at,
        )

    def _create_diff_evidence(
        self, incident_id: Any, commit: Any, diff: Any, repo_path: str
    ) -> Evidence:
        """Create evidence for a commit diff."""
        hunks_content = []
        for hunk in diff.hunks[:10]:  # Limit hunks
            hunks_content.append(
                f"--- {hunk.file_path} ---\n"
                f"@@ -{hunk.old_start},{hunk.old_count} "
                f"+{hunk.new_start},{hunk.new_count} @@\n"
                f"{hunk.content[:500]}"
            )

        content = (
            f"Diff for commit {commit.short_hash}\n"
            f"Files: {', '.join(diff.files_changed)}\n\n"
            + "\n\n".join(hunks_content)
        )

        evidence = Evidence(
            id=uuid4(),
            incident_id=incident_id,
            source_type=SourceType.GIT_DIFF,
            source_reference=f"{commit.hash}:{','.join(diff.files_changed[:3])}",
            content=content[:5000],  # Limit size
            timestamp=commit.date,
            metadata={
                "commit_hash": commit.hash,
                "files_changed": diff.files_changed,
                "hunk_count": len(diff.hunks),
            },
        )

        return self._evidence_repo.create_evidence(
            id=evidence.id,
            incident_id=evidence.incident_id,
            source_type=evidence.source_type.value,
            source_reference=evidence.source_reference,
            content=evidence.content,
            timestamp=evidence.timestamp,
            metadata=evidence.metadata,
            created_at=evidence.created_at,
        )

    def _is_candidate_change(
        self, commit: Any, stack_trace: str, service: str
    ) -> bool:
        """Determine if a commit is a candidate change.

        A commit is a candidate if:
        1. It modifies files referenced in the stack trace
        2. It modifies files in the same service
        3. It has a message suggesting a risky change
        """
        # Check stack trace correlation
        if stack_trace:
            matches = self._git_reader.match_stack_trace_files(
                stack_trace, [commit]
            )
            if matches:
                return True

        # Check file path correlation with service
        if service:
            service_lower = service.lower()
            for f in commit.files_changed:
                if service_lower in f.lower():
                    return True

        # Check commit message for risky keywords
        risky_keywords = [
            "deploy", "migration", "schema", "config",
            "env", "secret", "auth", "permission",
            "database", "cache", "timeout", "rate",
        ]
        msg_lower = commit.message.lower()
        for keyword in risky_keywords:
            if keyword in msg_lower:
                return True

        return False

    def _build_finding(
        self,
        incident_id: Any,
        candidate_commits: list[Any],
        all_commits: list[Any],
        evidence_ids: list[Any],
    ) -> AgentFinding:
        """Build a structured finding from git analysis."""
        if candidate_commits:
            finding_type = FindingType.CANDIDATE_CHANGE
            confidence = min(0.8, 0.3 + (len(candidate_commits) * 0.1))
        else:
            finding_type = FindingType.GENERAL
            confidence = 0.2

        # Build summary
        summary_parts = []
        summary_parts.append(f"Analyzed {len(all_commits)} recent commits")

        if candidate_commits:
            summary_parts.append(
                f"{len(candidate_commits)} candidate change(s) identified"
            )
            for c in candidate_commits[:3]:
                summary_parts.append(
                    f"  {c.short_hash}: {c.message[:80]} "
                    f"(files: {', '.join(c.files_changed[:2])})"
                )
        else:
            summary_parts.append("No candidate changes identified")

        summary = "; ".join(summary_parts)

        finding = AgentFinding(
            id=uuid4(),
            incident_id=incident_id,
            agent_name=self.name,
            finding_type=finding_type,
            summary=summary,
            confidence=confidence,
            evidence_ids=evidence_ids,
            metadata={
                "candidate_count": len(candidate_commits),
                "total_commits": len(all_commits),
            },
        )

        return self._finding_repo.create_finding(
            id=finding.id,
            incident_id=finding.incident_id,
            agent_name=finding.agent_name,
            finding_type=finding.finding_type.value,
            summary=finding.summary,
            confidence=finding.confidence,
            evidence_ids=finding.evidence_ids,
            created_at=finding.created_at,
            metadata=finding.metadata,
        )
