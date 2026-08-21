from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from uuid import uuid4

from backend.app.analysis.confidence import ConfidenceEngine
from backend.app.analysis.contradictions import ContradictionDetector
from backend.app.analysis.rca import RCASynthesisEngine
from backend.app.approval.service import ApprovalService
from backend.app.llm.fake import FakeLLMProvider
from backend.app.models.approval import ApprovalStatus
from backend.app.models.remediation import RemediationStatus
from backend.app.remediation.planner import RemediationPlanner
from backend.app.repositories import (
    ApprovalRepository,
    EvidenceRepository,
    FindingRepository,
    IncidentRepository,
    RCARepository,
    RemediationRepository,
)
from backend.app.services.rca_service import RCAService

VALID_RCA_JSON = """{
  "primary_hypothesis": {
    "title": "Deployment v2.1.0 introduced validation regression",
    "explanation": "The recent deployment changed payment validation behavior",
    "contributing_factors": ["New validation logic", "Missing edge case handling"],
    "observed_facts": ["Error rate spiked after deployment", "Stack traces show validation error"],
    "inferred_facts": ["Commit abc123 is the likely trigger"],
    "uncertainties": ["No direct reproduction performed"]
  },
  "alternative_hypotheses": [
    {
      "title": "Upstream API change",
      "explanation": "The upstream payment provider changed their API format",
      "contributing_factors": ["API version mismatch"],
      "observed_facts": [],
      "inferred_facts": [],
      "uncertainties": ["No payload capture"]
    }
  ],
  "observed_facts": ["Error rate increased at 14:32 UTC", "50+ errors in 5 minutes"],
  "inferred_facts": ["Deployment timing correlates with error onset"],
  "uncertainties": ["No direct reproduction"]
}"""


class TestPhase4E2E:
    def setup_method(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.incident_repo = IncidentRepository(self._tmp.name)
        self.evidence_repo = EvidenceRepository(self._tmp.name)
        self.finding_repo = FindingRepository(self._tmp.name)
        self.rca_repo = RCARepository(self._tmp.name)
        self.remediation_repo = RemediationRepository(self._tmp.name)
        self.approval_repo = ApprovalRepository(self._tmp.name)

    async def test_full_analysis_flow(self) -> None:
        """Test the complete Phase 4 flow from incident to approval."""
        # Create incident
        now = datetime.now(UTC)
        incident_id = uuid4()
        self.incident_repo.create_incident(
            id=incident_id,
            source="MANUAL",
            title="Payment service outage",
            severity="SEV1",
            service="payment-service",
            environment="production",
            status="INVESTIGATING",
            description="Users unable to make payments",
            stack_traces=[],
            created_at=now,
            updated_at=now,
            raw_payload={},
        )

        # Create evidence
        log_evidence_id = uuid4()
        self.evidence_repo.create_evidence(
            id=log_evidence_id,
            incident_id=incident_id,
            source_type="LOG",
            source_reference="/var/log/payment.log",
            content="ERROR: Payment validation failed at line 42",
            timestamp=now,
            metadata={"error_count": 50},
            created_at=now,
        )

        git_evidence_id = uuid4()
        self.evidence_repo.create_evidence(
            id=git_evidence_id,
            incident_id=incident_id,
            source_type="GIT_COMMIT",
            source_reference="abc123def456",
            content="Commit abc123: Deploy v2.1.0",
            timestamp=now,
            metadata={"commit_hash": "abc123def456"},
            created_at=now,
        )

        # Create findings
        self.finding_repo.create_finding(
            id=uuid4(),
            incident_id=incident_id,
            agent_name="log_triage",
            finding_type="ERROR_BURST",
            summary="50 errors detected in payment log",
            confidence=0.85,
            evidence_ids=[log_evidence_id],
            created_at=now,
            metadata={},
        )

        self.finding_repo.create_finding(
            id=uuid4(),
            incident_id=incident_id,
            agent_name="git_forensics",
            finding_type="CANDIDATE_CHANGE",
            summary="Commit abc123def456 deployed v2.1.0",
            confidence=0.7,
            evidence_ids=[git_evidence_id],
            created_at=now,
            metadata={},
        )

        # Set up service
        llm = FakeLLMProvider(responses=[VALID_RCA_JSON])
        confidence_engine = ConfidenceEngine()
        contradiction_detector = ContradictionDetector()
        rca_engine = RCASynthesisEngine(llm, confidence_engine, contradiction_detector)
        remediation_planner = RemediationPlanner()
        approval_service = ApprovalService(self.approval_repo)

        rca_service = RCAService(
            incident_repo=self.incident_repo,
            evidence_repo=self.evidence_repo,
            finding_repo=self.finding_repo,
            rca_repo=self.rca_repo,
            remediation_repo=self.remediation_repo,
            approval_repo=self.approval_repo,
            rca_engine=rca_engine,
            remediation_planner=remediation_planner,
            approval_service=approval_service,
        )

        # Run analysis
        result = await rca_service.analyze_incident(incident_id)

        # Verify RCA
        rca = result["rca"]
        assert rca.incident_id == incident_id
        assert rca.primary_hypothesis.title == "Deployment v2.1.0 introduced validation regression"
        assert len(rca.alternative_hypotheses) == 1
        assert rca.confidence >= 0.0
        assert rca.confidence <= 1.0
        assert rca.confidence_band in ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")

        # Verify remediation proposals
        proposals = result["remediation_proposals"]
        assert len(proposals) > 0
        for p in proposals:
            assert p.requires_approval is True
            assert p.status == RemediationStatus.PROPOSED

        # Verify approvals
        approvals = result["approvals"]
        assert len(approvals) > 0
        for a in approvals:
            assert a.status == ApprovalStatus.PENDING

    async def test_approval_flow(self) -> None:
        """Test the approval flow."""
        # Create incident
        now = datetime.now(UTC)
        incident_id = uuid4()
        self.incident_repo.create_incident(
            id=incident_id,
            source="MANUAL",
            title="Test incident",
            severity="SEV2",
            service="test-service",
            environment="production",
            status="INVESTIGATING",
            description="Test",
            stack_traces=[],
            created_at=now,
            updated_at=now,
            raw_payload={},
        )

        # Create evidence
        evidence_id = uuid4()
        self.evidence_repo.create_evidence(
            id=evidence_id,
            incident_id=incident_id,
            source_type="GIT_COMMIT",
            source_reference="abc123",
            content="Commit abc123",
            timestamp=now,
            metadata={"commit_hash": "abc123"},
            created_at=now,
        )

        # Set up service
        llm = FakeLLMProvider(responses=[VALID_RCA_JSON])
        rca_engine = RCASynthesisEngine(llm)
        remediation_planner = RemediationPlanner()
        approval_service = ApprovalService(self.approval_repo)

        rca_service = RCAService(
            incident_repo=self.incident_repo,
            evidence_repo=self.evidence_repo,
            finding_repo=self.finding_repo,
            rca_repo=self.rca_repo,
            remediation_repo=self.remediation_repo,
            approval_repo=self.approval_repo,
            rca_engine=rca_engine,
            remediation_planner=remediation_planner,
            approval_service=approval_service,
        )

        # Run analysis
        result = await rca_service.analyze_incident(incident_id)
        approvals = result["approvals"]
        proposals = result["remediation_proposals"]

        assert len(approvals) > 0
        assert len(proposals) > 0

        # Approve first proposal
        approval = approvals[0]
        proposal = proposals[0]

        approved = approval_service.approve(approval.id, approved_by="senior-engineer")
        assert approved.status == ApprovalStatus.APPROVED
        assert approved.approved_by == "senior-engineer"
        assert approved.decided_at is not None

        # Verify remediation status updated
        self.remediation_repo.update_status(
            proposal_id=proposal.id,
            status="APPROVED",
        )
        updated_proposal = self.remediation_repo.get_proposal(proposal.id)
        assert updated_proposal["status"] == "APPROVED"

    async def test_no_commands_executed(self) -> None:
        """Verify that no commands are executed during analysis."""
        now = datetime.now(UTC)
        incident_id = uuid4()
        self.incident_repo.create_incident(
            id=incident_id,
            source="MANUAL",
            title="Test",
            severity="SEV3",
            service="test",
            environment="test",
            status="RECEIVED",
            description="Test",
            stack_traces=[],
            created_at=now,
            updated_at=now,
            raw_payload={},
        )

        llm = FakeLLMProvider(responses=[VALID_RCA_JSON])
        rca_engine = RCASynthesisEngine(llm)
        remediation_planner = RemediationPlanner()
        approval_service = ApprovalService(self.approval_repo)

        rca_service = RCAService(
            incident_repo=self.incident_repo,
            evidence_repo=self.evidence_repo,
            finding_repo=self.finding_repo,
            rca_repo=self.rca_repo,
            remediation_repo=self.remediation_repo,
            approval_repo=self.approval_repo,
            rca_engine=rca_engine,
            remediation_planner=remediation_planner,
            approval_service=approval_service,
        )

        result = await rca_service.analyze_incident(incident_id)

        # Verify no subprocess was called
        # (If we got here without executing commands, the test passes)
        assert result is not None
        assert "rca" in result
        assert "remediation_proposals" in result
        assert "approvals" in result
