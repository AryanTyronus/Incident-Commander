from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.agents.git_forensics import GitForensicsAgent
from backend.app.models.agent_schemas import InvestigationState
from backend.app.models.evidence import SourceType
from backend.app.repositories import (
    EvidenceRepository,
    FindingRepository,
    IncidentRepository,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"


def _create_test_incident(repo: IncidentRepository, incident_id: uuid4) -> dict:
    """Create a test incident to satisfy FK constraints."""
    return repo.create_incident(
        id=incident_id,
        source="MANUAL",
        title="Test Incident",
        severity="SEV1",
        service="test-service",
        environment="production",
        status="RECEIVED",
        description="Test incident",
        stack_traces=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        raw_payload={},
    )


class TestGitForensicsAgent:
    """Tests for the GitForensicsAgent."""

    def setup_method(self) -> None:
        self.db_path = tempfile.mktemp(suffix=".db")
        self.incident_repo = IncidentRepository(self.db_path)
        self.evidence_repo = EvidenceRepository(self.db_path)
        self.finding_repo = FindingRepository(self.db_path)

    def teardown_method(self) -> None:
        self.incident_repo.close()
        self.evidence_repo.close()
        self.finding_repo.close()
        Path(self.db_path).unlink(missing_ok=True)

    def _make_context(
        self, incident_id: uuid4, repo_path: str | None = None, **extra
    ) -> InvestigationContext:
        state = InvestigationState(incident_id=incident_id)
        extra_dict = dict(extra)
        if repo_path:
            extra_dict["repo_path"] = repo_path
        return InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=state,
            extra=extra_dict,
        )

    async def test_analyze_recent_commits(self) -> None:
        agent = GitForensicsAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        repo_path = str(FIXTURES_DIR / "repos" / "demo-service")
        context = self._make_context(incident_id, repo_path)

        result = await agent.run(context)

        assert result.agent_name == "git_forensics"
        assert result.confidence > 0.1
        assert result.findings is not None
        assert len(result.findings) > 0

    async def test_identify_candidate_change(self) -> None:
        agent = GitForensicsAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        repo_path = str(FIXTURES_DIR / "repos" / "demo-service")
        context = self._make_context(
            incident_id, repo_path, service="payment"
        )

        result = await agent.run(context)

        assert result.metadata.get("candidate_commits", 0) > 0

    async def test_commit_evidence_persisted(self) -> None:
        agent = GitForensicsAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        repo_path = str(FIXTURES_DIR / "repos" / "demo-service")
        context = self._make_context(incident_id, repo_path)

        await agent.run(context)

        evidence = self.evidence_repo.list_for_incident(incident_id)
        commit_evidence = [
            e for e in evidence if e["source_type"] == SourceType.GIT_COMMIT.value
        ]
        assert len(commit_evidence) > 0

    async def test_no_repo_path(self) -> None:
        agent = GitForensicsAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        context = self._make_context(incident_id)

        result = await agent.run(context)
        assert result.confidence == 0.0
        assert "No repository path" in result.summary

    async def test_nonexistent_repo(self) -> None:
        agent = GitForensicsAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        context = self._make_context(incident_id, "/nonexistent/repo")

        result = await agent.run(context)
        assert result.confidence == 0.0

    async def test_stack_trace_correlation(self) -> None:
        agent = GitForensicsAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        repo_path = str(FIXTURES_DIR / "repos" / "demo-service")
        stack_trace = 'File "/app/payment/service.py", line 10'
        context = self._make_context(
            incident_id, repo_path, stack_trace=stack_trace
        )

        result = await agent.run(context)

        assert result.metadata.get("candidate_commits", 0) > 0
