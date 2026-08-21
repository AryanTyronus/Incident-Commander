from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.app.approval.policies import ApprovalPolicy
from backend.app.models.approval import Approval, ApprovalStatus


class DuplicateDecisionError(Exception):
    """Raised when a duplicate decision is attempted."""


class InvalidDecisionError(Exception):
    """Raised when an invalid decision is attempted."""


class ApprovalNotFoundError(Exception):
    """Raised when an approval is not found."""


class ApprovalService:
    """Service for managing remediation approvals.

    Responsibilities:
    - Create approval requests
    - Approve proposals
    - Reject proposals
    - Prevent duplicate decisions
    - Record approver and timestamps
    """

    def __init__(self, approval_repo: Any) -> None:
        self._repo = approval_repo
        self._policy = ApprovalPolicy()

    def create_approval(
        self,
        *,
        remediation_id: UUID,
        incident_id: UUID,
    ) -> Approval:
        """Create a new approval request."""
        now = datetime.now(UTC)
        approval = Approval(
            id=uuid4(),
            remediation_id=remediation_id,
            incident_id=incident_id,
            status=ApprovalStatus.PENDING,
            created_at=now,
        )

        self._repo.create_approval(
            id=approval.id,
            remediation_id=approval.remediation_id,
            incident_id=approval.incident_id,
            status=approval.status.value,
            approved_by=None,
            created_at=approval.created_at,
            decided_at=None,
        )

        return approval

    def approve(
        self,
        approval_id: UUID,
        *,
        approved_by: str,
    ) -> Approval:
        """Approve a remediation proposal."""
        approval = self._repo.get_approval(approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval not found: {approval_id}")

        current_status = ApprovalStatus(approval["status"])

        if not self._policy.can_approve(
            Approval(
                remediation_id=approval["remediation_id"],
                incident_id=approval["incident_id"],
                status=current_status,
            )
        ):
            raise DuplicateDecisionError(
                f"Approval {approval_id} cannot be approved "
                f"(current status: {current_status.value})"
            )

        now = datetime.now(UTC)
        self._repo.update_approval(
            approval_id=approval_id,
            status=ApprovalStatus.APPROVED.value,
            approved_by=approved_by,
            decided_at=now,
        )

        result = self._repo.get_approval(approval_id)
        return Approval(**result)  # type: ignore

    def reject(
        self,
        approval_id: UUID,
        *,
        rejected_by: str,
    ) -> Approval:
        """Reject a remediation proposal."""
        approval = self._repo.get_approval(approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval not found: {approval_id}")

        current_status = ApprovalStatus(approval["status"])

        if not self._policy.can_reject(
            Approval(
                remediation_id=approval["remediation_id"],
                incident_id=approval["incident_id"],
                status=current_status,
            )
        ):
            raise DuplicateDecisionError(
                f"Approval {approval_id} cannot be rejected "
                f"(current status: {current_status.value})"
            )

        now = datetime.now(UTC)
        self._repo.update_approval(
            approval_id=approval_id,
            status=ApprovalStatus.REJECTED.value,
            approved_by=rejected_by,
            decided_at=now,
        )

        result = self._repo.get_approval(approval_id)
        return Approval(**result)  # type: ignore

    def get_approval(self, approval_id: UUID) -> Approval | None:
        """Get an approval by ID."""
        result = self._repo.get_approval(approval_id)
        if result is None:
            return None
        return Approval(**result)

    def get_by_remediation_id(self, remediation_id: UUID) -> Approval | None:
        """Get an approval by remediation ID."""
        result = self._repo.get_by_remediation_id(remediation_id)
        if result is None:
            return None
        return Approval(**result)
