from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.agents.log_triage import LogTriageAgent
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


class TestLogTriageAgent:
    """Tests for the LogTriageAgent."""

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
        self, incident_id: uuid4, log_path: str | None = None, **extra
    ) -> InvestigationContext:
        state = InvestigationState(incident_id=incident_id)
        extra_dict = dict(extra)
        if log_path:
            extra_dict["log_path"] = log_path
        return InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=state,
            extra=extra_dict,
        )

    async def test_analyze_incident_log(self) -> None:
        agent = LogTriageAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        log_path = str(FIXTURES_DIR / "logs" / "incident.log")
        context = self._make_context(incident_id, log_path)

        result = await agent.run(context)

        assert result.agent_name == "log_triage"
        assert result.confidence > 0.3
        assert result.findings is not None
        assert len(result.findings) > 0

        evidence = self.evidence_repo.list_for_incident(incident_id)
        assert len(evidence) > 0
        assert any(e["source_type"] == SourceType.LOG.value for e in evidence)

    async def test_detect_burst(self) -> None:
        agent = LogTriageAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        log_path = str(FIXTURES_DIR / "logs" / "incident.log")
        context = self._make_context(incident_id, log_path)

        result = await agent.run(context)

        assert result.metadata.get("error_count", 0) > 10

    async def test_detect_stack_trace(self) -> None:
        agent = LogTriageAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        log_path = str(FIXTURES_DIR / "logs" / "incident.log")
        context = self._make_context(incident_id, log_path)

        await agent.run(context)

        evidence = self.evidence_repo.list_for_incident(incident_id)
        stack_traces = [
            e for e in evidence if e["source_type"] == SourceType.STACK_TRACE.value
        ]
        assert len(stack_traces) > 0

    async def test_no_log_path(self) -> None:
        agent = LogTriageAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        context = self._make_context(incident_id)

        result = await agent.run(context)
        assert result.confidence == 0.0
        assert "No log file path" in result.summary

    async def test_file_not_found(self) -> None:
        agent = LogTriageAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        context = self._make_context(incident_id, "/nonexistent/log.txt")

        result = await agent.run(context)
        assert result.confidence == 0.0

    async def test_findings_persisted(self) -> None:
        agent = LogTriageAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        log_path = str(FIXTURES_DIR / "logs" / "incident.log")
        context = self._make_context(incident_id, log_path)

        await agent.run(context)

        findings = self.finding_repo.list_for_incident(incident_id)
        assert len(findings) > 0
        finding = findings[0]
        assert finding["agent_name"] == "log_triage"
        assert len(finding["evidence_ids"]) > 0
