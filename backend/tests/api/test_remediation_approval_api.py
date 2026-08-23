"""Tests for the remediation approval HTTP routes.

The frontend posts approval decisions to ``/api/remediations/{id}/approve`` and
``/api/remediations/{id}/reject`` with the engineer id as a query parameter.
These routes were declared on the incidents router, so they were served under
``/api/incidents/remediations/...`` and every decision returned 404.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.approval import ApprovalStatus
from backend.app.repositories import (
    ApprovalRepository,
    IncidentRepository,
    RCARepository,
    RemediationRepository,
)

ENGINEER = "demo-engineer"


def _seed_proposal_awaiting_approval(db_path: str) -> tuple[UUID, UUID]:
    """Create an incident, an RCA, a PROPOSED remediation and a PENDING approval."""
    incident_id = uuid4()
    rca_id = uuid4()
    remediation_id = uuid4()
    approval_id = uuid4()
    now = datetime.now(UTC)

    incident_repo = IncidentRepository(db_path)
    rca_repo = RCARepository(db_path)
    remediation_repo = RemediationRepository(db_path)
    approval_repo = ApprovalRepository(db_path)
    try:
        incident_repo.create_incident(
            id=incident_id,
            source="MANUAL",
            title="Payment service outage - validation regression",
            severity="SEV1",
            service="payment-service",
            environment="production",
            status="INVESTIGATING",
            description="Negative amounts passing validation",
            stack_traces=[],
            created_at=now,
            updated_at=now,
            raw_payload={},
        )
        rca_repo.create_rca(
            id=rca_id,
            incident_id=incident_id,
            report_json="{}",
            created_at=now,
            updated_at=now,
        )
        remediation_repo.create_proposal(
            id=remediation_id,
            incident_id=incident_id,
            rca_id=rca_id,
            type="ROLLBACK",
            title="Revert commit 7666d11",
            description="Revert the validation boundary change",
            rationale="The regression was introduced there",
            expected_effect="Validation rejects negative amounts again",
            risks=["Reverts the release"],
            prerequisites=["Confirm no dependent deploys"],
            commands=["git revert 7666d11 --no-edit"],
            patch_summary="",
            evidence_ids=[],
            requires_approval=True,
            status="PROPOSED",
            created_at=now,
        )
        approval_repo.create_approval(
            id=approval_id,
            remediation_id=remediation_id,
            incident_id=incident_id,
            status=ApprovalStatus.PENDING.value,
            approved_by=None,
            created_at=now,
            decided_at=None,
        )
    finally:
        incident_repo.close()
        rca_repo.close()
        remediation_repo.close()
        approval_repo.close()

    return remediation_id, approval_id


def _proposal_status(db_path: str, remediation_id: UUID) -> str:
    repo = RemediationRepository(db_path)
    try:
        return repo.get_proposal(remediation_id)["status"]
    finally:
        repo.close()


def _stored_approval(db_path: str, approval_id: UUID) -> dict:
    repo = ApprovalRepository(db_path)
    try:
        return repo.get_approval(approval_id)
    finally:
        repo.close()


class TestRoutesMatchTheFrontend:
    """The registered paths must be exactly the ones the client posts to."""

    def test_decision_routes_are_registered_at_the_api_remediations_prefix(self) -> None:
        # Assert against the OpenAPI path map, not ``app.routes``: it is the
        # app's published route contract, so it reports the paths a client can
        # actually post to regardless of how FastAPI represents an included
        # router internally.
        paths = app.openapi()["paths"]

        assert "/api/remediations/{remediation_id}/approve" in paths
        assert "post" in paths["/api/remediations/{remediation_id}/approve"]

        assert "/api/remediations/{remediation_id}/reject" in paths
        assert "post" in paths["/api/remediations/{remediation_id}/reject"]

    def test_decision_routes_are_not_nested_under_incidents(self) -> None:
        """Guards against re-declaring them on the /api/incidents router."""
        nested = [
            getattr(route, "path", "")
            for route in app.routes
            if "/api/incidents/remediations" in getattr(route, "path", "")
        ]

        assert nested == []


class TestRejectRemediation:
    """The exact request the Reject button produces."""

    def test_reject_with_query_parameter_engineer_id(
        self, client: TestClient, tmp_db: str
    ) -> None:
        remediation_id, approval_id = _seed_proposal_awaiting_approval(tmp_db)

        resp = client.post(
            f"/api/remediations/{remediation_id}/reject?rejected_by={ENGINEER}"
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["remediation_id"] == str(remediation_id)
        assert body["approval_id"] == str(approval_id)
        assert body["status"] == ApprovalStatus.REJECTED.value
        assert body["approved_by"] == ENGINEER
        assert body["decided_at"] is not None

    def test_rejection_is_recorded_with_engineer_and_timestamp(
        self, client: TestClient, tmp_db: str
    ) -> None:
        remediation_id, approval_id = _seed_proposal_awaiting_approval(tmp_db)

        client.post(f"/api/remediations/{remediation_id}/reject?rejected_by={ENGINEER}")

        stored = _stored_approval(tmp_db, approval_id)
        assert stored["status"] == ApprovalStatus.REJECTED.value
        assert stored["approved_by"] == ENGINEER
        assert stored["decided_at"] is not None
        assert _proposal_status(tmp_db, remediation_id) == "REJECTED"

    def test_unknown_remediation_returns_404(self, client: TestClient, tmp_db: str) -> None:
        resp = client.post(f"/api/remediations/{uuid4()}/reject?rejected_by={ENGINEER}")

        assert resp.status_code == 404
        # Distinct from a missing route: the endpoint ran and found no approval.
        assert resp.json()["detail"] == "Approval not found"

    def test_second_rejection_is_refused(self, client: TestClient, tmp_db: str) -> None:
        remediation_id, approval_id = _seed_proposal_awaiting_approval(tmp_db)
        client.post(f"/api/remediations/{remediation_id}/reject?rejected_by={ENGINEER}")

        resp = client.post(
            f"/api/remediations/{remediation_id}/reject?rejected_by=someone-else"
        )

        assert resp.status_code == 409
        assert "cannot be rejected" in resp.json()["detail"]
        # The original decision stands.
        stored = _stored_approval(tmp_db, approval_id)
        assert stored["approved_by"] == ENGINEER


class TestApproveRemediation:
    """The Approve button posts to the matching route."""

    def test_approve_with_query_parameter_engineer_id(
        self, client: TestClient, tmp_db: str
    ) -> None:
        remediation_id, approval_id = _seed_proposal_awaiting_approval(tmp_db)

        resp = client.post(
            f"/api/remediations/{remediation_id}/approve?approved_by={ENGINEER}"
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["approval_id"] == str(approval_id)
        assert body["status"] == ApprovalStatus.APPROVED.value
        assert body["approved_by"] == ENGINEER
        assert body["decided_at"] is not None

    def test_approval_records_authorization_without_executing(
        self, client: TestClient, tmp_db: str
    ) -> None:
        remediation_id, approval_id = _seed_proposal_awaiting_approval(tmp_db)

        resp = client.post(
            f"/api/remediations/{remediation_id}/approve?approved_by={ENGINEER}"
        )

        # Approval is an authorization record; nothing is run against production.
        assert "No execution has occurred" in resp.json()["message"]
        assert _stored_approval(tmp_db, approval_id)["approved_by"] == ENGINEER
        assert _proposal_status(tmp_db, remediation_id) == "APPROVED"

    def test_unknown_remediation_returns_404(self, client: TestClient, tmp_db: str) -> None:
        resp = client.post(f"/api/remediations/{uuid4()}/approve?approved_by={ENGINEER}")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Approval not found"

    def test_rejected_proposal_cannot_be_approved(
        self, client: TestClient, tmp_db: str
    ) -> None:
        remediation_id, _ = _seed_proposal_awaiting_approval(tmp_db)
        client.post(f"/api/remediations/{remediation_id}/reject?rejected_by={ENGINEER}")

        resp = client.post(
            f"/api/remediations/{remediation_id}/approve?approved_by={ENGINEER}"
        )

        assert resp.status_code == 409
        assert _proposal_status(tmp_db, remediation_id) == "REJECTED"

    def test_second_approval_is_refused(self, client: TestClient, tmp_db: str) -> None:
        remediation_id, _ = _seed_proposal_awaiting_approval(tmp_db)
        client.post(f"/api/remediations/{remediation_id}/approve?approved_by={ENGINEER}")

        resp = client.post(
            f"/api/remediations/{remediation_id}/approve?approved_by=someone-else"
        )

        assert resp.status_code == 409
        assert "cannot be approved" in resp.json()["detail"]
