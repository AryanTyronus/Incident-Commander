from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.agents.git_forensics import GitForensicsAgent
from backend.app.agents.log_triage import LogTriageAgent
from backend.app.agents.runbook import RunbookAgent
from backend.app.models.agent_schemas import InvestigationState
from backend.app.models.evidence import SourceType
from backend.app.repositories import (
    EvidenceRepository,
    FindingRepository,
    IncidentRepository,
)
from backend.app.retrieval.chroma import ChromaRetrieval
from backend.app.retrieval.embeddings import FakeEmbeddingProvider
from backend.app.tools.runbook_search import RunbookSearch

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


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


class TestPhase3EndToEnd:
    """End-to-end test for Phase 3 forensic investigation.

    Scenario: INC-TEST-003
    - Known deployment (v2.1.0)
    - Known error burst (PaymentError: Gateway timeout)
    - Known stack trace (payment/service.py)
    - Known matching runbook (payment-failures.md)
    """

    def setup_method(self) -> None:
        self.db_path = tempfile.mktemp(suffix=".db")
        self.incident_repo = IncidentRepository(self.db_path)
        self.evidence_repo = EvidenceRepository(self.db_path)
        self.finding_repo = FindingRepository(self.db_path)
        self.chroma_dir = tempfile.mkdtemp()
        self.provider = FakeEmbeddingProvider()
        self.retrieval = ChromaRetrieval(
            embedding_provider=self.provider,
            collection_name="e2e_test",
            persist_directory=self.chroma_dir,
        )
        self.search = RunbookSearch(self.retrieval)
        runbooks_dir = FIXTURES_DIR / "runbooks"
        if runbooks_dir.exists():
            self.search.index_runbooks(runbooks_dir)

    def teardown_method(self) -> None:
        self.incident_repo.close()
        self.evidence_repo.close()
        self.finding_repo.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_full_investigation(self) -> None:
        """Run all three agents and verify the complete forensic pipeline."""
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)

        state = InvestigationState(incident_id=incident_id)

        # --- Log Triage Agent ---
        log_agent = LogTriageAgent(self.evidence_repo, self.finding_repo)
        log_context = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=state,
            extra={"log_path": str(FIXTURES_DIR / "logs" / "incident.log")},
        )
        log_result = await log_agent.run(log_context)

        # --- Git Forensics Agent ---
        git_agent = GitForensicsAgent(self.evidence_repo, self.finding_repo)
        git_context = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=state,
            extra={
                "repo_path": str(FIXTURES_DIR / "repos" / "demo-service"),
                "stack_trace": 'File "/app/payment/service.py", line 10',
                "service": "payment",
            },
        )
        git_result = await git_agent.run(git_context)

        # --- Runbook Agent ---
        runbook_agent = RunbookAgent(
            self.evidence_repo, self.finding_repo, self.search
        )
        runbook_context = InvestigationContext(
            incident_id=incident_id,
            incident={
                "service": "payment-service",
                "title": "Payment failures",
                "description": "PaymentError: Gateway timeout after deployment",
            },
            state=state,
            extra={},
        )
        runbook_result = await runbook_agent.run(runbook_context)

        # --- Assertions ---

        # All three agents should complete successfully
        assert log_result.agent_name == "log_triage"
        assert log_result.confidence > 0.3

        assert git_result.agent_name == "git_forensics"
        assert git_result.confidence > 0.1

        assert runbook_result.agent_name == "runbook"
        assert runbook_result.confidence > 0.2

        # --- Evidence verification ---

        all_evidence = self.evidence_repo.list_for_incident(incident_id)
        assert len(all_evidence) > 0

        # Should have LOG evidence
        log_evidence = [
            e for e in all_evidence if e["source_type"] == SourceType.LOG.value
        ]
        assert len(log_evidence) > 0
        assert log_evidence[0]["source_reference"] != ""

        # Should have STACK_TRACE evidence
        stack_evidence = [
            e for e in all_evidence if e["source_type"] == SourceType.STACK_TRACE.value
        ]
        assert len(stack_evidence) > 0

        # Should have GIT_COMMIT evidence
        commit_evidence = [
            e for e in all_evidence if e["source_type"] == SourceType.GIT_COMMIT.value
        ]
        assert len(commit_evidence) > 0

        # Should have RUNBOOK evidence
        runbook_evidence = [
            e for e in all_evidence if e["source_type"] == SourceType.RUNBOOK.value
        ]
        assert len(runbook_evidence) > 0

        # --- Finding verification ---

        all_findings = self.finding_repo.list_for_incident(incident_id)
        assert len(all_findings) >= 3  # One per agent

        for finding in all_findings:
            assert finding["agent_name"] in ("log_triage", "git_forensics", "runbook")
            assert 0.0 <= finding["confidence"] <= 1.0
            assert finding["summary"]
            assert len(finding["evidence_ids"]) > 0

        # --- Evidence provenance verification ---

        evidence_id_map = {str(e["id"]): e for e in all_evidence}

        for finding in all_findings:
            for eid in finding["evidence_ids"]:
                assert str(eid) in evidence_id_map, (
                    f"Finding {finding['id']} references evidence {eid} "
                    "that does not exist"
                )

        # --- Verify the expected incident scenario ---

        # Should detect the error burst
        assert log_result.metadata.get("error_count", 0) > 10

        # Should identify the candidate change
        assert git_result.metadata.get("candidate_commits", 0) > 0

        # Should find relevant runbooks
        assert runbook_result.metadata.get("relevant_results", 0) > 0

    async def test_agent_failure_isolation(self) -> None:
        """Verify that one agent failing doesn't destroy other results."""
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        state = InvestigationState(incident_id=incident_id)

        # Log agent should succeed
        log_agent = LogTriageAgent(self.evidence_repo, self.finding_repo)
        log_context = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=state,
            extra={"log_path": str(FIXTURES_DIR / "logs" / "incident.log")},
        )
        log_result = await log_agent.run(log_context)
        assert log_result.confidence > 0.3

        # Git agent should fail (no repo_path)
        git_agent = GitForensicsAgent(self.evidence_repo, self.finding_repo)
        git_context = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=state,
            extra={},
        )
        git_result = await git_agent.run(git_context)
        assert git_result.confidence == 0.0

        # Runbook agent should succeed
        runbook_agent = RunbookAgent(
            self.evidence_repo, self.finding_repo, self.search
        )
        runbook_context = InvestigationContext(
            incident_id=incident_id,
            incident={
                "service": "payment-service",
                "title": "Payment failures",
            },
            state=state,
            extra={},
        )
        runbook_result = await runbook_agent.run(runbook_context)
        assert runbook_result.confidence > 0.2

        # Verify both successful agents produced evidence
        all_evidence = self.evidence_repo.list_for_incident(incident_id)
        assert len(all_evidence) > 0

        # Verify findings exist
        all_findings = self.finding_repo.list_for_incident(incident_id)
        assert len(all_findings) >= 2
