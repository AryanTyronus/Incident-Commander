from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.approval.policies import ApprovalPolicy
from backend.app.approval.service import (
    ApprovalService,
    DuplicateDecisionError,
)
from backend.app.models.approval import Approval, ApprovalStatus
from backend.app.repositories import (
    ApprovalRepository,
    IncidentRepository,
    RCARepository,
    RemediationRepository,
)


class TestApprovalPolicy:
    def test_requires_approval(self) -> None:
        assert ApprovalPolicy.requires_approval(None) is True

    def test_can_approve_pending(self) -> None:
        approval = Approval(
            remediation_id=uuid4(),
            incident_id=uuid4(),
            status=ApprovalStatus.PENDING,
        )
        assert ApprovalPolicy.can_approve(approval) is True

    def test_cannot_approve_approved(self) -> None:
        approval = Approval(
            remediation_id=uuid4(),
            incident_id=uuid4(),
            status=ApprovalStatus.APPROVED,
        )
        assert ApprovalPolicy.can_approve(approval) is False

    def test_can_reject_pending(self) -> None:
        approval = Approval(
            remediation_id=uuid4(),
            incident_id=uuid4(),
            status=ApprovalStatus.PENDING,
        )
        assert ApprovalPolicy.can_reject(approval) is True

    def test_cannot_reject_approved(self) -> None:
        approval = Approval(
            remediation_id=uuid4(),
            incident_id=uuid4(),
            status=ApprovalStatus.APPROVED,
        )
        assert ApprovalPolicy.can_reject(approval) is False

    def test_validate_decision(self) -> None:
        assert ApprovalPolicy.validate_decision(
            ApprovalStatus.PENDING, ApprovalStatus.APPROVED
        ) is True
        assert ApprovalPolicy.validate_decision(
            ApprovalStatus.PENDING, ApprovalStatus.REJECTED
        ) is True
        assert ApprovalPolicy.validate_decision(
            ApprovalStatus.APPROVED, ApprovalStatus.REJECTED
        ) is False
        assert ApprovalPolicy.validate_decision(
            ApprovalStatus.REJECTED, ApprovalStatus.APPROVED
        ) is False


class TestApprovalService:
    def setup_method(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.repo = ApprovalRepository(self._tmp.name)
        self.remediation_repo = RemediationRepository(self._tmp.name)
        self.rca_repo = RCARepository(self._tmp.name)
        self.incident_repo = IncidentRepository(self._tmp.name)
        self.service = ApprovalService(self.repo)
        # Create incident, RCA report, and remediation proposal for FK references
        self.incident_id = uuid4()
        now = datetime.now(UTC)
        self.incident_repo.create_incident(
            id=self.incident_id,
            source="MANUAL",
            title="Test incident",
            severity="SEV2",
            service="test",
            environment="test",
            status="RECEIVED",
            description="Test",
            stack_traces=[],
            created_at=now,
            updated_at=now,
            raw_payload={},
        )
        self.rca_repo.create_rca(
            id=uuid4(),
            incident_id=self.incident_id,
            report_json='{"primary_hypothesis": {"title": "Test"}}',
            created_at=now,
            updated_at=now,
        )
        self.rca_id = self.rca_repo.get_by_incident_id(self.incident_id)["id"]
        self.remediation_repo.create_proposal(
            id=uuid4(),
            incident_id=self.incident_id,
            rca_id=self.rca_id,
            type="INVESTIGATION",
            title="Test proposal",
            description="Test",
            rationale="Test",
            expected_effect="Test",
            risks=[],
            prerequisites=[],
            commands=[],
            patch_summary="",
            evidence_ids=[],
            requires_approval=True,
            status="PROPOSED",
            created_at=now,
        )
        self.proposal_id = self.remediation_repo.list_for_incident(self.incident_id)[0]["id"]

    def test_create_approval(self) -> None:
        approval = self.service.create_approval(
            remediation_id=self.proposal_id,
            incident_id=self.incident_id,
        )
        assert approval.status == ApprovalStatus.PENDING
        assert approval.id is not None

    def test_approve(self) -> None:
        approval = self.service.create_approval(
            remediation_id=self.proposal_id,
            incident_id=self.incident_id,
        )
        approved = self.service.approve(approval.id, approved_by="engineer")
        assert approved.status == ApprovalStatus.APPROVED
        assert approved.approved_by == "engineer"
        assert approved.decided_at is not None

    def test_reject(self) -> None:
        approval = self.service.create_approval(
            remediation_id=self.proposal_id,
            incident_id=self.incident_id,
        )
        rejected = self.service.reject(approval.id, rejected_by="engineer")
        assert rejected.status == ApprovalStatus.REJECTED
        assert rejected.approved_by == "engineer"

    def test_duplicate_approval_rejected(self) -> None:
        approval = self.service.create_approval(
            remediation_id=self.proposal_id,
            incident_id=self.incident_id,
        )
        self.service.approve(approval.id, approved_by="engineer")
        with pytest.raises(DuplicateDecisionError):
            self.service.approve(approval.id, approved_by="engineer2")

    def test_duplicate_rejection_rejected(self) -> None:
        approval = self.service.create_approval(
            remediation_id=self.proposal_id,
            incident_id=self.incident_id,
        )
        self.service.reject(approval.id, rejected_by="engineer")
        with pytest.raises(DuplicateDecisionError):
            self.service.reject(approval.id, rejected_by="engineer2")

    def test_approve_after_reject_rejected(self) -> None:
        approval = self.service.create_approval(
            remediation_id=self.proposal_id,
            incident_id=self.incident_id,
        )
        self.service.reject(approval.id, rejected_by="engineer")
        with pytest.raises(DuplicateDecisionError):
            self.service.approve(approval.id, approved_by="engineer2")

    def test_persistence(self) -> None:
        approval = self.service.create_approval(
            remediation_id=self.proposal_id,
            incident_id=self.incident_id,
        )
        # Create new service instance
        service2 = ApprovalService(ApprovalRepository(self._tmp.name))
        loaded = service2.get_approval(approval.id)
        assert loaded is not None
        assert loaded.status == ApprovalStatus.PENDING
