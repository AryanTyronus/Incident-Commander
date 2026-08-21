from __future__ import annotations

from typing import Any

from backend.app.models.approval import Approval, ApprovalStatus


class ApprovalPolicy:
    """Approval policies for remediation proposals.

    Every remediation proposal requires explicit human approval.
    """

    @staticmethod
    def requires_approval(proposal: Any) -> bool:
        """Determine if a proposal requires approval.

        All proposals require approval. No exceptions.
        """
        return True

    @staticmethod
    def can_approve(approval: Approval) -> bool:
        """Check if an approval can be approved."""
        return approval.status == ApprovalStatus.PENDING

    @staticmethod
    def can_reject(approval: Approval) -> bool:
        """Check if an approval can be rejected."""
        return approval.status == ApprovalStatus.PENDING

    @staticmethod
    def validate_decision(
        current_status: ApprovalStatus,
        new_status: ApprovalStatus,
    ) -> bool:
        """Validate a status transition.

        Only PENDING -> APPROVED or PENDING -> REJECTED is allowed.
        """
        if current_status == ApprovalStatus.PENDING:
            return new_status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED)
        return False
